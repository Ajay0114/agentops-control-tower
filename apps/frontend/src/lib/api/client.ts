"use client";

// Centralized browser-side API client. Every Client Component that needs
// dashboard data calls through here, never `fetch` directly - and always
// against this app's own /api/* routes, never the FastAPI backend
// directly. See docs/architecture/m7-dashboard-and-auth.md for why.

import type {
  AgentResponse,
  AgentVersionResponse,
  CurrentUser,
  DashboardOverview,
  EnvironmentResponse,
  ExecutionResponse,
  Paginated,
  SessionResponse,
  TelemetryEventListResponse,
} from "@/lib/types";

export class ApiClientError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch<T>(
  path: string,
  params?: Record<string, string | number | undefined | null>,
  init?: RequestInit
): Promise<{ data: T; totalCount: number | null }> {
  const url = new URL(path, window.location.origin);

  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const response = await fetch(url.toString(), {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;

    try {
      const body = await response.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      // Response body wasn't JSON - fall back to the generic message above.
    }

    throw new ApiClientError(response.status, detail);
  }

  if (response.status === 204) {
    return { data: undefined as T, totalCount: null };
  }

  const data = (await response.json()) as T;
  const totalCountHeader = response.headers.get("X-Total-Count");

  return { data, totalCount: totalCountHeader !== null ? Number(totalCountHeader) : null };
}

function readCsrfCookie(): string {
  const match = document.cookie.match(/(?:^|; )agentops_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

// --- Auth ---------------------------------------------------------------

export async function login(email: string, password: string): Promise<{ user: CurrentUser }> {
  const { data } = await apiFetch<{ user: CurrentUser }>("/api/auth/login", undefined, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-csrf-token": readCsrfCookie() },
    body: JSON.stringify({ email, password }),
  });
  return data;
}

export async function logout(): Promise<void> {
  await apiFetch("/api/auth/logout", undefined, {
    method: "POST",
    headers: { "x-csrf-token": readCsrfCookie() },
  });
}

// --- Agents ---------------------------------------------------------------

export async function fetchAgents(params: {
  environment_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<AgentResponse[]> {
  const { data } = await apiFetch<AgentResponse[]>("/api/agents", params);
  return data;
}

export async function fetchAgent(id: string): Promise<AgentResponse> {
  const { data } = await apiFetch<AgentResponse>(`/api/agents/${id}`);
  return data;
}

export async function fetchAgentVersions(
  id: string,
  params: { limit?: number; offset?: number } = {}
): Promise<AgentVersionResponse[]> {
  const { data } = await apiFetch<AgentVersionResponse[]>(`/api/agents/${id}/versions`, params);
  return data;
}

// --- Environments -----------------------------------------------------

export async function fetchEnvironments(
  params: { project_id?: string; limit?: number; offset?: number } = {}
): Promise<EnvironmentResponse[]> {
  const { data } = await apiFetch<EnvironmentResponse[]>("/api/environments", params);
  return data;
}

export async function fetchEnvironment(id: string): Promise<EnvironmentResponse> {
  const { data } = await apiFetch<EnvironmentResponse>(`/api/environments/${id}`);
  return data;
}

// --- Sessions ---------------------------------------------------------

export async function fetchSessions(
  params: {
    project_id?: string;
    environment_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  } = {}
): Promise<SessionResponse[]> {
  const { data } = await apiFetch<SessionResponse[]>("/api/sessions", params);
  return data;
}

export async function fetchSession(id: string): Promise<SessionResponse> {
  const { data } = await apiFetch<SessionResponse>(`/api/sessions/${id}`);
  return data;
}

// --- Executions ---------------------------------------------------------

export interface ExecutionFilters {
  // The index signature is required for this named interface (unlike the
  // other fetch* functions' inline parameter types) to satisfy apiFetch's
  // Record<string, ...>-typed params parameter - TS does not consider a
  // named interface without one assignable there even when every declared
  // property's value type already fits.
  [key: string]: string | number | undefined;
  session_id?: string;
  agent_id?: string;
  environment_id?: string;
  status?: string;
  execution_id?: string;
  started_after?: string;
  started_before?: string;
  limit?: number;
  offset?: number;
}

export async function fetchExecutions(
  params: ExecutionFilters
): Promise<Paginated<ExecutionResponse>> {
  const { data, totalCount } = await apiFetch<ExecutionResponse[]>("/api/executions", params);
  return { items: data, total: totalCount };
}

export async function fetchExecution(id: string): Promise<ExecutionResponse> {
  const { data } = await apiFetch<ExecutionResponse>(`/api/executions/${id}`);
  return data;
}

export async function fetchExecutionEvents(
  id: string,
  params: { page?: number; page_size?: number } = {}
): Promise<TelemetryEventListResponse> {
  const { data } = await apiFetch<TelemetryEventListResponse>(
    `/api/executions/${id}/events`,
    params
  );
  return data;
}

// --- Traces ---------------------------------------------------------------

export async function fetchTraceEvents(
  traceId: string,
  params: { page?: number; page_size?: number } = {}
): Promise<TelemetryEventListResponse> {
  const { data } = await apiFetch<TelemetryEventListResponse>(
    `/api/traces/${traceId}/events`,
    params
  );
  return data;
}

// --- Dashboard ---------------------------------------------------------

export async function fetchDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await apiFetch<DashboardOverview>("/api/dashboard/overview");
  return data;
}
