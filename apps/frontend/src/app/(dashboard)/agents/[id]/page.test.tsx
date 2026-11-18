import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";

import { renderAsync } from "@/test/render-async";
import AgentDetailPage from "./page";
import { ApiClientError } from "@/lib/api/client";
import type { AgentResponse, AgentVersionResponse } from "@/lib/types";

const fetchAgentMock = vi.fn();
const fetchAgentVersionsMock = vi.fn();
const createAgentVersionMock = vi.fn();

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    fetchAgent: (...args: unknown[]) => fetchAgentMock(...args),
    fetchAgentVersions: (...args: unknown[]) => fetchAgentVersionsMock(...args),
    createAgentVersion: (...args: unknown[]) => createAgentVersionMock(...args),
  };
});

function makeAgent(overrides: Partial<AgentResponse> = {}): AgentResponse {
  return {
    id: "agent-1",
    environment_id: "env-1",
    name: "Support Agent",
    slug: "support-agent",
    description: null,
    framework: "custom",
    status: "registered",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeVersion(overrides: Partial<AgentVersionResponse> = {}): AgentVersionResponse {
  return {
    id: "version-1",
    agent_id: "agent-1",
    version: "1.0.0",
    description: null,
    configuration: null,
    deployment_status: "draft",
    deployed_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  fetchAgentMock.mockReset();
  fetchAgentVersionsMock.mockReset();
  createAgentVersionMock.mockReset();
});

describe("AgentDetailPage", () => {
  it("renders the agent and its version history", async () => {
    fetchAgentMock.mockResolvedValue(makeAgent());
    fetchAgentVersionsMock.mockResolvedValue([makeVersion()]);

    await renderAsync(<AgentDetailPage params={Promise.resolve({ id: "agent-1" })} />);

    await waitFor(() => expect(screen.getByText("Support Agent")).toBeInTheDocument());
    expect(screen.getByText("1.0.0")).toBeInTheDocument();
  });

  it("creates a new version and shows it in the refreshed list", async () => {
    fetchAgentMock.mockResolvedValue(makeAgent());
    fetchAgentVersionsMock
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([makeVersion({ version: "2.0.0" })]);
    createAgentVersionMock.mockResolvedValue(makeVersion({ version: "2.0.0" }));

    await renderAsync(<AgentDetailPage params={Promise.resolve({ id: "agent-1" })} />);

    await waitFor(() => expect(screen.getByText("No versions yet")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /add version/i }));
    fireEvent.change(screen.getByLabelText("Version"), { target: { value: "2.0.0" } });
    fireEvent.click(screen.getByRole("button", { name: "Create version" }));

    await waitFor(() =>
      expect(createAgentVersionMock).toHaveBeenCalledWith("agent-1", {
        version: "2.0.0",
        description: undefined,
      })
    );
    await waitFor(() => expect(screen.getByText("2.0.0")).toBeInTheDocument());
  });

  it("shows a validation error when submitting the version form with no version string", async () => {
    fetchAgentMock.mockResolvedValue(makeAgent());
    fetchAgentVersionsMock.mockResolvedValue([]);

    await renderAsync(<AgentDetailPage params={Promise.resolve({ id: "agent-1" })} />);
    await waitFor(() => expect(screen.getByText("No versions yet")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /add version/i }));
    fireEvent.click(screen.getByRole("button", { name: "Create version" }));

    expect(screen.getByText("Version is required.")).toBeInTheDocument();
    expect(createAgentVersionMock).not.toHaveBeenCalled();
  });

  it("shows an error state for an unknown agent", async () => {
    fetchAgentMock.mockRejectedValue(new ApiClientError(404, "Agent not found"));
    fetchAgentVersionsMock.mockResolvedValue([]);

    await renderAsync(<AgentDetailPage params={Promise.resolve({ id: "missing" })} />);

    await waitFor(() => expect(screen.getByText("Agent not found")).toBeInTheDocument());
  });
});
