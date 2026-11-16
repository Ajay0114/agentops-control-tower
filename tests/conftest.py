import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from agentops_api.db import get_db
from agentops_api.main import app
from agentops_api.models.base import Base
from agentops_api.models import core  # noqa: F401 - registers ORM models


# Derive the test connection from the configured database URL,
# but explicitly target the isolated test database.
database_url = make_url(
    __import__("agentops_api.config", fromlist=["get_settings"])
    .get_settings()
    .database_url
).set(database="agentops_test")

if database_url.database != "agentops_test":
    raise RuntimeError("Refusing to run tests against a non-test database")

test_engine = create_engine(
    database_url,
    pool_pre_ping=True,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture(scope="function", autouse=True)
def prepare_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()

        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
