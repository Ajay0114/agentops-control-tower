import { apiGet } from "./api-client";

export type ExecutionStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

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

export async function getExecutions(
  limit = 50,
  offset = 0
): Promise<ExecutionResponse[]> {
  return apiGet<ExecutionResponse[]>(
    `/api/v1/executions?limit=${limit}&offset=${offset}`
  );
}

export async function getExecution(
  executionId: string
): Promise<ExecutionResponse> {
  return apiGet<ExecutionResponse>(
    `/api/v1/executions/${executionId}`
  );
}