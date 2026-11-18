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

/**
 * Whether local login can be skipped entirely. This is a two-part,
 * fail-closed check - BOTH must hold, and neither can be forced by
 * anything a browser request supplies:
 *
 * 1. `LOCAL_AUTH_BYPASS=true` - an explicit, deliberate operator opt-in.
 *    Off by default.
 * 2. `process.env.NODE_ENV !== "production"` - Next.js itself sets this to
 *    "production" for `next build`/`next start`, and to "development" for
 *    `next dev`. This is not a value anything in this app's own config can
 *    override, which is what makes it an actual security boundary rather
 *    than another flag someone could mis-set: a production build *cannot*
 *    bypass login, full stop, regardless of what LOCAL_AUTH_BYPASS is set
 *    to in its environment.
 *
 * The existing session/cookie/CSRF login implementation is untouched and
 * fully intact behind this - see lib/server/session.ts's getCurrentUser(),
 * which is the only place this flag is actually consulted.
 */
export function isLocalAuthBypassActive(): boolean {
  return process.env.LOCAL_AUTH_BYPASS === "true" && process.env.NODE_ENV !== "production";
}

/**
 * The synthetic identity used while the bypass above is active. Its
 * organization_id/project_id are display-only placeholders, exactly like a
 * real User's - see session.ts's module comment: no data request is ever
 * authorized by what this object says, only by AGENTOPS_API_KEY.
 */
export const LOCAL_BYPASS_USER = {
  id: "local-bypass",
  organization_id: "local-development",
  project_id: null,
  email: "local-developer@localhost",
  role: "admin",
  status: "active",
  last_login_at: null,
  organization_name: "Local Development",
  project_name: null,
} as const;
