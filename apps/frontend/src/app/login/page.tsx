
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Command } from "lucide-react";

import { login, ApiClientError } from "@/lib/api/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login(email, password);
      router.push("/");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.status === 429) {
          setError("Too many login attempts. Try again in a few minutes.");
        } else if (err.status === 401) {
          setError("Invalid email or password.");
        } else {
          setError("Something went wrong. Please try again.");
        }
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#090e19] px-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-800 bg-slate-900/60 p-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-[#334e9b] text-white">
            <Command size={20} />
          </div>
          <div>
            <div className="font-semibold text-slate-100">AgentOps</div>
            <div className="text-xs tracking-wide text-slate-500">CONTROL TOWER</div>
          </div>
        </div>

        <h1 className="mb-1 text-lg font-medium text-slate-100">Sign in</h1>
        <p className="mb-6 text-sm text-slate-400">Local administrator access.</p>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="mb-1 block text-sm text-slate-300">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1 block text-sm text-slate-300">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-400">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-slate-500">
          New here?{" "}
          <a href="/signup" className="text-blue-400 hover:text-blue-300">
            Create an organization
          </a>
        </p>
      </div>
    </div>
  );
}
