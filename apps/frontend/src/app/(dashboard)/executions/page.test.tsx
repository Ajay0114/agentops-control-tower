import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import ExecutionsPage from "./page";
import { ApiClientError } from "@/lib/api/client";
import type { ExecutionResponse } from "@/lib/types";

const fetchExecutionsMock = vi.fn();
const fetchEnvironmentsMock = vi.fn();
const pushMock = vi.fn();
let searchParamsValue = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParamsValue,
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    fetchExecutions: (...args: unknown[]) => fetchExecutionsMock(...args),
    fetchEnvironments: (...args: unknown[]) => fetchEnvironmentsMock(...args),
  };
});

function makeExecution(overrides: Partial<ExecutionResponse>): ExecutionResponse {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    session_id: "session-1",
    agent_id: "agent-1",
    agent_version_id: null,
    external_execution_id: "ext-1",
    status: "completed",
    started_at: "2026-01-01T00:00:00Z",
    ended_at: "2026-01-01T00:00:05Z",
    duration_ms: 5000,
    error_type: null,
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:05Z",
    ...overrides,
  };
}

beforeEach(() => {
  fetchExecutionsMock.mockReset();
  fetchEnvironmentsMock.mockReset();
  fetchEnvironmentsMock.mockResolvedValue([]);
  pushMock.mockClear();
  searchParamsValue = new URLSearchParams();
});

describe("ExecutionsPage", () => {
  it("renders the execution list with status and duration", async () => {
    fetchExecutionsMock.mockResolvedValue({
      items: [makeExecution({})],
      total: 1,
    });

    render(<ExecutionsPage />);

    await waitFor(() => expect(screen.getByText("completed")).toBeInTheDocument());
    expect(screen.getByText("5.0s")).toBeInTheDocument();
  });

  it("shows an empty state when no executions match the filters", async () => {
    fetchExecutionsMock.mockResolvedValue({ items: [], total: 0 });

    render(<ExecutionsPage />);

    await waitFor(() =>
      expect(screen.getByText("No executions match these filters")).toBeInTheDocument()
    );
  });

  it("shows an error state when the request fails", async () => {
    fetchExecutionsMock.mockRejectedValue(new ApiClientError(401, "Unauthorized"));

    render(<ExecutionsPage />);

    await waitFor(() => expect(screen.getByText("Unauthorized")).toBeInTheDocument());
  });

  it("only forwards execution_id as a filter when the search box holds a valid UUID", async () => {
    searchParamsValue = new URLSearchParams({ q: "not-a-uuid" });
    fetchExecutionsMock.mockResolvedValue({ items: [], total: 0 });

    render(<ExecutionsPage />);

    await waitFor(() => expect(fetchExecutionsMock).toHaveBeenCalled());
    const callArgs = fetchExecutionsMock.mock.calls[0][0];
    expect(callArgs.execution_id).toBeUndefined();
  });

  it("forwards a valid UUID from the search box as execution_id", async () => {
    searchParamsValue = new URLSearchParams({
      q: "11111111-1111-1111-1111-111111111111",
    });
    fetchExecutionsMock.mockResolvedValue({ items: [], total: 0 });

    render(<ExecutionsPage />);

    await waitFor(() =>
      expect(fetchExecutionsMock).toHaveBeenCalledWith(
        expect.objectContaining({ execution_id: "11111111-1111-1111-1111-111111111111" })
      )
    );
  });

  it("forwards the agent_id filter from the URL", async () => {
    searchParamsValue = new URLSearchParams({ agent_id: "agent-42" });
    fetchExecutionsMock.mockResolvedValue({ items: [], total: 0 });

    render(<ExecutionsPage />);

    await waitFor(() =>
      expect(fetchExecutionsMock).toHaveBeenCalledWith(
        expect.objectContaining({ agent_id: "agent-42" })
      )
    );
  });
});
