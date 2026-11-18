import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { setNodeEnv } from "@/test/set-node-env";
import { isLocalAuthBypassActive } from "./env";

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("isLocalAuthBypassActive", () => {
  it("is off by default (no LOCAL_AUTH_BYPASS set)", () => {
    delete process.env.LOCAL_AUTH_BYPASS;
    setNodeEnv("development");
    expect(isLocalAuthBypassActive()).toBe(false);
  });

  it("is on only when explicitly set to the literal string 'true' in a non-production build", () => {
    process.env.LOCAL_AUTH_BYPASS = "true";
    setNodeEnv("development");
    expect(isLocalAuthBypassActive()).toBe(true);
  });

  it("treats any other value as off (e.g. a typo, or a truthy-looking but wrong string)", () => {
    process.env.LOCAL_AUTH_BYPASS = "1";
    setNodeEnv("development");
    expect(isLocalAuthBypassActive()).toBe(false);
  });

  it("fails closed in a production build even if the flag is set to true - this is the actual security boundary", () => {
    process.env.LOCAL_AUTH_BYPASS = "true";
    setNodeEnv("production");
    expect(isLocalAuthBypassActive()).toBe(false);
  });

  it("is off in test NODE_ENV too if the flag isn't set", () => {
    delete process.env.LOCAL_AUTH_BYPASS;
    setNodeEnv("test");
    expect(isLocalAuthBypassActive()).toBe(false);
  });
});
