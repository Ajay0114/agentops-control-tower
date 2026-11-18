import "server-only";

import { randomBytes } from "node:crypto";
import { cookies } from "next/headers";

import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME, isProduction } from "./env";

/**
 * Double-submit cookie CSRF protection for the two state-changing routes
 * this app has (login, logout). The CSRF cookie is deliberately NOT
 * HttpOnly - the browser's JS needs to read it and echo it back as a
 * header, which is exactly what makes the pattern work: a cross-site
 * attacker's form submission carries the session cookie automatically but
 * cannot read this cookie's value to also set the matching header.
 */

export async function ensureCsrfCookie(): Promise<string> {
  const store = await cookies();
  const existing = store.get(CSRF_COOKIE_NAME)?.value;

  if (existing) {
    return existing;
  }

  const token = randomBytes(32).toString("base64url");

  store.set(CSRF_COOKIE_NAME, token, {
    httpOnly: false,
    secure: isProduction,
    sameSite: "lax",
    path: "/",
  });

  return token;
}

export async function verifyCsrf(request: Request): Promise<boolean> {
  const store = await cookies();
  const cookieValue = store.get(CSRF_COOKIE_NAME)?.value;
  const headerValue = request.headers.get(CSRF_HEADER_NAME);

  return Boolean(cookieValue) && cookieValue === headerValue;
}

export { CSRF_COOKIE_NAME, CSRF_HEADER_NAME };
