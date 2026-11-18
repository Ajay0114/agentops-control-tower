import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { setNodeEnv } from "@/test/set-node-env";
import { proxy } from "./proxy";

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

function makeRequest(path: string, cookies: Record<string, string> = {}): NextRequest {
  const request = new NextRequest(new URL(path, "http://localhost:3000"));

  for (const [name, value] of Object.entries(cookies)) {
    request.cookies.set(name, value);
  }

  return request;
}

describe("proxy (protected-route gate)", () => {
  it("redirects an unauthenticated request for a protected page to /login", () => {
    const response = proxy(makeRequest("/executions"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("does not redirect a request that carries a session cookie", () => {
    const response = proxy(makeRequest("/executions", { agentops_session: "some-token" }));

    expect(response.headers.get("location")).toBeNull();
  });

  it("never redirects the login page itself, even with no session cookie", () => {
    const response = proxy(makeRequest("/login"));

    expect(response.headers.get("location")).toBeNull();
  });

  it("never redirects the signup page itself, even with no session cookie", () => {
    const response = proxy(makeRequest("/signup"));

    expect(response.headers.get("location")).toBeNull();
  });

  it("never redirects the login API route, so the login form can always submit", () => {
    const response = proxy(makeRequest("/api/auth/login"));

    expect(response.headers.get("location")).toBeNull();
  });

  it("never redirects the logout API route, even with no session cookie", () => {
    const response = proxy(makeRequest("/api/auth/logout"));

    expect(response.headers.get("location")).toBeNull();
  });

  it("never redirects a data API route either, so an unauthenticated fetch gets the route handler's own JSON 401 instead of login-page HTML", () => {
    const response = proxy(makeRequest("/api/dashboard/overview"));

    expect(response.headers.get("location")).toBeNull();
  });

  it("sets a CSRF cookie on first visit when one is not already present", () => {
    const response = proxy(makeRequest("/login"));

    expect(response.cookies.get("agentops_csrf")).toBeDefined();
  });

  it("does not overwrite an existing CSRF cookie", () => {
    const response = proxy(makeRequest("/login", { agentops_csrf: "existing-token" }));

    // NextResponse.next()/redirect() only sets a NEW cookie on the response
    // when we explicitly call .set(); since the request already carries one,
    // the response here carries none of its own for that cookie name.
    expect(response.cookies.get("agentops_csrf")).toBeUndefined();
  });
});

describe("proxy (local-auth bypass)", () => {
  it("does not redirect a protected page to /login when the bypass is active, even with no session cookie", () => {
    process.env.LOCAL_AUTH_BYPASS = "true";
    setNodeEnv("development");

    const response = proxy(makeRequest("/executions"));

    expect(response.headers.get("location")).toBeNull();
  });

  it("redirects /login itself to / when the bypass is active", () => {
    process.env.LOCAL_AUTH_BYPASS = "true";
    setNodeEnv("development");

    const response = proxy(makeRequest("/login"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/");
  });

  it("redirects /signup itself to / when the bypass is active", () => {
    process.env.LOCAL_AUTH_BYPASS = "true";
    setNodeEnv("development");

    const response = proxy(makeRequest("/signup"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/");
  });

  it("fails closed in a production build: still redirects to /login even with the bypass flag set", () => {
    process.env.LOCAL_AUTH_BYPASS = "true";
    setNodeEnv("production");

    const response = proxy(makeRequest("/executions"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("does not redirect /login to / in a production build even with the flag set", () => {
    process.env.LOCAL_AUTH_BYPASS = "true";
    setNodeEnv("production");

    const response = proxy(makeRequest("/login"));

    expect(response.headers.get("location")).toBeNull();
  });
});
