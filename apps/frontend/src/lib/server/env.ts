import "server-only";

// Server-only configuration. The `server-only` import above makes any
// accidental import of this module from a Client Component fail the build,
// since AGENTOPS_API_KEY in particular must never reach the browser bundle.

function requireEnv(name: string): string {
  const value = process.env[name];

  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. See apps/frontend/.env.example.`
    );
  }

  return value;
}

export const BACKEND_API_URL = (
  process.env.BACKEND_API_URL || "http://localhost:8010"
).replace(/\/+$/, "");

/**
 * Lazily read so a missing key only breaks requests that actually need it
 * (e.g. this lets `next build` succeed without the key present), rather than
 * crashing module evaluation for every import of this file.
 */
export function getBackendApiKey(): string {
  return requireEnv("AGENTOPS_API_KEY");
}

export const SESSION_COOKIE_NAME = "agentops_session";
export const CSRF_COOKIE_NAME = "agentops_csrf";
export const CSRF_HEADER_NAME = "x-csrf-token";

export const isProduction = process.env.NODE_ENV === "production";
