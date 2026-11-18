// Next.js's own global types declare `process.env.NODE_ENV` read-only
// (it's normally only ever set by the toolchain itself), which is correct
// for application code but gets in the way of tests that specifically need
// to exercise behavior across different NODE_ENV values (e.g. proving the
// local-auth bypass fails closed in a production build). This is the one
// sanctioned place to cast around that.
export function setNodeEnv(value: "development" | "production" | "test"): void {
  (process.env as { NODE_ENV: string }).NODE_ENV = value;
}
