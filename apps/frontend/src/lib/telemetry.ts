
import { apiGet } from "./api-client";

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
  model_usage: {
    provider?: string;
    model?: string;
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
    cost_usd?: number | string;
  } | null;
  error: {
    type?: string;
    code?: string;
    message?: string;
    retryable?: boolean;
  } | null;
  payload: Record<string, unknown> | null;
  attributes: Record<string, unknown>;
  event_data: Record<string, unknown>;
}

export interface TelemetryResponse {
  items: TelemetryEvent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export async function getTelemetryEvents(
  page = 1,
  pageSize = 50
): Promise<TelemetryResponse> {
  return apiGet<TelemetryResponse>(
    `/api/v1/telemetry/events?page=${page}&page_size=${pageSize}`
  );
}
