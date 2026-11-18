// Resolution stub for the `server-only` package under Vitest - see
// vitest.config.ts's alias entry. The real package intentionally throws
// when its "browser" package.json condition is resolved, which is exactly
// what we want in a real browser bundle (catching an accidental import of
// server-only code from a Client Component) but Vitest's jsdom
// environment also resolves that condition, so every file under
// lib/server/ would throw just by importing this guard - even though
// Vitest is really running in Node, not a browser. This stub is a no-op,
// matching the real package's actual server-side (non-"browser") behavior.
export {};
