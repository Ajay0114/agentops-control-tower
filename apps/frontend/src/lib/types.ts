// Shared frontend types, mirroring the backend's Pydantic response schemas
// exactly (apps/api/src/agentops_api/schemas/*.py). Keep these in sync by
// hand when the backend schemas change - there is no shared codegen between
// the two languages in this project.

export type ExecutionStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface EnvironmentResponse {
  id: string;
  project_id: string;
  name: string;
  slug: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentResponse {
  id: string;
  environment_id: string;
  name: string;
  slug: string;
  description: string | null;
  framework: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AgentVersionResponse {
  id: string;
  agent_id: string;
  version: string;
  description: string | null;
  configuration: Record<string, unknown> | null;
  deployment_status: string;
  deployed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionResponse {
  id: string;
  project_id: string;
  environment_id: string;
  external_session_id: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionResponse {
  id: string;
  session_id: string;
  agent_id: string;
  agent_version_id: string | null;
  external_execution_id: string | null;
  status: ExecutionStatus;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  error_type: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModelUsage {
  provider?: string;
  model?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  cost_usd?: number | string;
}

export interface TelemetryError {
  type?: string;
  code?: string;
  message?: string;
  retryable?: boolean;
}

export interface TelemetryEvent {
  id: string;
  organization_id: string;
  event_id: string;
  schema_version: string;
  event_type: string;
  occurred_at: string;
  received_at: string;
  agent_id: string;
  agent_version_id: string | null;
  session_id: string;
  execution_id: string;
  source_platform: string;
  service_name: string;
  environment: string;
  operation_name: string;
  operation_kind: string;
  operation_status: string;
  duration_ms: number | null;
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  model_usage: ModelUsage | null;
  error: TelemetryError | null;
  payload: Record<string, unknown> | null;
  attributes: Record<string, unknown>;
  event_data: Record<string, unknown>;
}

export interface TelemetryEventListResponse {
  items: TelemetryEvent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ExecutionTrendPoint {
  date: string;
  count: number;
}

export interface DashboardOverview {
  total_executions: number;
  running_executions: number;
  completed_executions: number;
  failed_executions: number;
  queued_executions: number;
  cancelled_executions: number;
  success_rate: number | null;
  total_agents: number;
  total_tokens_used: number | null;
  recent_executions: ExecutionResponse[];
  recent_agents: AgentResponse[];
  execution_trend: ExecutionTrendPoint[];
}

export interface CurrentUser {
  id: string;
  organization_id: string;
  project_id: string | null;
  email: string;
  role: string;
  status: string;
  last_login_at: string | null;
}

export interface Paginated<T> {
  items: T[];
  total: number | null;
}
