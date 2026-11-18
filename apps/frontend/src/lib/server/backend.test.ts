import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ORIGINAL_ENV = { ...process.env };

const cookieStore = {
  get: vi.fn(),
};

vi.mock("next/headers", () => ({
  cookies: async () => cookieStore,
}));

const fetchMock = vi.fn();

beforeEach(() => {
  process.env = { ...ORIGINAL_ENV, AGENTOPS_API_KEY: "aops_internal_test_key" };
  cookieStore.get.mockReset();
  fetchMock.mockReset();
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    text: async () => JSON.stringify({ ok: true }),
    headers: new Headers(),
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
  vi.unstubAllGlobals();
});

describe("backendRequest", () => {
  it("sends the caller's own session token when one exists, never the internal key", async () => {
    cookieStore.get.mockReturnValue({ value: "asess_abc123_realtoken" });

    const { backendRequest } = await import("./backend");
    await backendRequest("/api/v1/agents");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["X-Session-Token"]).toBe("asess_abc123_realtoken");
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("falls back to this deployment's own internal API key when there is no session", async () => {
    cookieStore.get.mockReturnValue(undefined);

    const { backendRequest } = await import("./backend");
    await backendRequest("/api/v1/agents");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer aops_internal_test_key");
    expect(init.headers["X-Session-Token"]).toBeUndefined();
  });
});
