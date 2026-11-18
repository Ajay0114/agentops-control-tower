import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setNodeEnv } from "@/test/set-node-env";

const ORIGINAL_ENV = { ...process.env };

const authBackendRequestMock = vi.fn();

vi.mock("./backend", async () => {
  const actual = await vi.importActual<typeof import("./backend")>("./backend");
  return { ...actual, authBackendRequest: authBackendRequestMock };
});

const cookieStore = {
  get: vi.fn(),
  set: vi.fn(),
  delete: vi.fn(),
};

vi.mock("next/headers", () => ({
  cookies: async () => cookieStore,
}));

beforeEach(() => {
  process.env = { ...ORIGINAL_ENV };
  authBackendRequestMock.mockReset();
  cookieStore.get.mockReset();
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("getCurrentUser with the local-auth bypass", () => {
  it("returns the synthetic bypass user without calling the backend at all, when the bypass is active", async () => {
    process.env.LOCAL_AUTH_BYPASS = "true";
    setNodeEnv("development");

    const { getCurrentUser } = await import("./session");
    const user = await getCurrentUser();

    expect(user).not.toBeNull();
    expect(user!.email).toBe("local-developer@localhost");
    expect(authBackendRequestMock).not.toHaveBeenCalled();
    expect(cookieStore.get).not.toHaveBeenCalled();
  });

  it("falls back to the real cookie/session check when the bypass is not active", async () => {
    process.env.LOCAL_AUTH_BYPASS = "false";
    setNodeEnv("development");
    cookieStore.get.mockReturnValue(undefined);

    const { getCurrentUser } = await import("./session");
    const user = await getCurrentUser();

    expect(user).toBeNull();
    expect(cookieStore.get).toHaveBeenCalled();
  });

  it("never activates the bypass in a production build, even with the flag set", async () => {
    process.env.LOCAL_AUTH_BYPASS = "true";
    setNodeEnv("production");
    cookieStore.get.mockReturnValue(undefined);

    const { getCurrentUser } = await import("./session");
    const user = await getCurrentUser();

    // Falls through to the real check, which (no cookie) returns null -
    // never the synthetic bypass user.
    expect(user).toBeNull();
    expect(cookieStore.get).toHaveBeenCalled();
  });
});
