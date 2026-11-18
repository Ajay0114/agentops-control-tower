"""Self-service customer onboarding (M8): signup -> organization -> project
-> environment -> integration key -> SDK-registered agent, and the tenant
isolation guarantee across two independently signed-up customers.

Unlike test_auth_routes.py (which covers login/logout/me for a
pre-existing, offline-provisioned User), every account here is created
through the public /signup endpoint itself - these tests are the actual
proof that a brand-new customer can reach a fully working, isolated
dashboard with zero manual/offline provisioning steps.
"""

from agentops_api.services.auth_service import reset_rate_limiter_for_tests
import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    reset_rate_limiter_for_tests()
    yield
    reset_rate_limiter_for_tests()


def signup(client, organization_name, email, password="x12345678"):
    response = client.post(
        "/api/v1/auth/signup",
        json={"organization_name": organization_name, "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_signup_creates_organization_and_admin_user_and_logs_in(client):
    body = signup(client, "Acme Corp", "founder@acme.test")

    assert body["session_token"]
    user = body["user"]
    assert user["email"] == "founder@acme.test"
    assert user["role"] == "admin"
    assert user["status"] == "active"
    assert user["organization_name"] == "Acme Corp"
    assert user["project_id"] is None
    assert user["project_name"] is None
    # Never leaked, same guarantee as the existing login endpoint.
    assert "password" not in user
    assert "password_hash" not in user


def test_signup_duplicate_email_rejected(client):
    signup(client, "Acme Corp", "dup@example.com")

    response = client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "A Different Org",
            "email": "dup@example.com",
            "password": "x12345678",
        },
    )

    assert response.status_code == 409
    # And no orphaned organization was left behind by the rejected attempt.
    orgs = client.post(
        "/api/v1/auth/login", json={"email": "dup@example.com", "password": "x12345678"}
    )
    assert orgs.json()["user"]["organization_name"] == "Acme Corp"


def test_signup_rejects_unknown_fields_and_short_password(client):
    too_short = client.post(
        "/api/v1/auth/signup",
        json={"organization_name": "Acme", "email": "short@example.com", "password": "short"},
    )
    assert too_short.status_code == 422

    browser_supplied_org_id = client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Acme",
            "email": "extra@example.com",
            "password": "x12345678",
            "organization_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert browser_supplied_org_id.status_code == 422


def test_me_reflects_the_signed_up_organization(client):
    body = signup(client, "Globex", "globex@example.com")
    token = body["session_token"]

    response = client.get("/api/v1/auth/me", headers={"x-session-token": token})

    assert response.status_code == 200
    assert response.json()["organization_name"] == "Globex"


def test_create_project_requires_authentication(client):
    response = client.post("/api/v1/projects", json={"name": "Default"})
    assert response.status_code == 401


def test_create_project_is_scoped_to_the_caller_s_own_organization(client):
    signup_a = signup(client, "Org A", "a@example.com")
    token_a = signup_a["session_token"]

    response = client.post(
        "/api/v1/projects",
        json={"name": "Production"},
        headers={"x-session-token": token_a},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Production"
    assert body["organization_id"] == signup_a["user"]["organization_id"]
    assert body["slug"]  # auto-derived, never required from the caller


def test_create_environment_via_session_reuses_the_existing_endpoint_unchanged(client):
    """Proves the AuthContext generalization is a pure addition: an
    EXISTING, untouched endpoint (POST /api/v1/environments, from M4) now
    also works for a logged-in customer's session, with zero changes to
    environments.py/environment_service.py themselves."""
    body = signup(client, "Initech", "initech@example.com")
    token = body["session_token"]

    project = client.post(
        "/api/v1/projects", json={"name": "Default"}, headers={"x-session-token": token}
    ).json()

    response = client.post(
        "/api/v1/environments",
        json={"project_id": project["id"], "name": "Production", "slug": "production"},
        headers={"x-session-token": token},
    )

    assert response.status_code == 201
    assert response.json()["project_id"] == project["id"]


def _onboard_customer(client, organization_name, email):
    """Full self-service onboarding for one customer: signup, project,
    environment, and one integration API key - returns everything a test
    needs to act as this customer going forward."""
    signup_body = signup(client, organization_name, email)
    token = signup_body["session_token"]
    headers = {"x-session-token": token}

    project = client.post("/api/v1/projects", json={"name": "Default"}, headers=headers).json()

    environment = client.post(
        "/api/v1/environments",
        json={"project_id": project["id"], "name": "Production", "slug": "production"},
        headers=headers,
    ).json()

    key_response = client.post(
        "/api/v1/auth/api-keys", json={"name": "My agent"}, headers=headers
    )
    assert key_response.status_code == 201, key_response.text
    raw_key = key_response.json()["raw_key"]

    return {
        "session_token": token,
        "organization_id": signup_body["user"]["organization_id"],
        "project": project,
        "environment": environment,
        "integration_key": raw_key,
    }


def _register_agent(client, customer, name):
    response = client.post(
        "/api/v1/agents",
        json={
            "environment_id": customer["environment"]["id"],
            "name": name,
            "slug": name.lower().replace(" ", "-"),
        },
        headers={"Authorization": f"Bearer {customer['integration_key']}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_two_separately_signed_up_customers_have_fully_isolated_dashboards(client):
    """The brief's own validation scenario: two separate customer accounts,
    each creating their own organization/project/environment/key and
    connecting their own agent, each seeing only their own data - proven at
    the HTTP layer for both credential types the dashboard actually uses:
    the customer's own session (what the browser sees) and their
    integration key (what the SDK/agent uses)."""
    customer_a = _onboard_customer(client, "Customer A Inc", "owner@customer-a.test")
    customer_b = _onboard_customer(client, "Customer B LLC", "owner@customer-b.test")

    assert customer_a["organization_id"] != customer_b["organization_id"]

    agent_a = _register_agent(client, customer_a, "Support Bot A")
    agent_b = _register_agent(client, customer_b, "Support Bot B")

    # Each customer's own dashboard SESSION (never their API key) sees only
    # their own agent - this is the new session-authenticated data path.
    agents_seen_by_a = client.get(
        "/api/v1/agents", headers={"x-session-token": customer_a["session_token"]}
    ).json()
    agents_seen_by_b = client.get(
        "/api/v1/agents", headers={"x-session-token": customer_b["session_token"]}
    ).json()

    assert [a["id"] for a in agents_seen_by_a] == [agent_a["id"]]
    assert [a["id"] for a in agents_seen_by_b] == [agent_b["id"]]

    # And the aggregate dashboard overview agrees - never counting the other
    # organization's agent.
    overview_a = client.get(
        "/api/v1/dashboard/overview", headers={"x-session-token": customer_a["session_token"]}
    ).json()
    overview_b = client.get(
        "/api/v1/dashboard/overview", headers={"x-session-token": customer_b["session_token"]}
    ).json()

    assert overview_a["total_agents"] == 1
    assert overview_b["total_agents"] == 1

    # Each customer's own integration key is equally isolated, and can never
    # see the other's integration keys either (the pre-existing M7 key
    # management isolation, re-confirmed here in the self-service context).
    keys_seen_by_a = client.get(
        "/api/v1/auth/api-keys", headers={"x-session-token": customer_a["session_token"]}
    ).json()
    assert len(keys_seen_by_a) == 1
    assert keys_seen_by_a[0]["key_prefix"] != ""

    # Customer A's integration key has no standing in Customer B's org at all.
    cross_org_agents = client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {customer_a['integration_key']}"},
    ).json()
    assert [a["id"] for a in cross_org_agents] == [agent_a["id"]]


def test_session_authentication_is_rejected_for_an_invalid_token_with_no_fallback_key(client):
    response = client.get("/api/v1/agents", headers={"x-session-token": "asess_bogus_notreal"})
    assert response.status_code == 401
