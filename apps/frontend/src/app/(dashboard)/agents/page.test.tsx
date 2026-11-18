import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import AgentsPage from "./page";
import { ApiClientError } from "@/lib/api/client";
import type { AgentResponse } from "@/lib/types";

const fetchAgentsMock = vi.fn();
let searchParamsValue = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParamsValue,
}));

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return { ...actual, fetchAgents: (...args: unknown[]) => fetchAgentsMock(...args) };
});

function makeAgent(overrides: Partial<AgentResponse>): AgentResponse {
  return {
    id: "agent-1",
    environment_id: "env-1",
    name: "Support Agent",
    slug: "support-agent",
    description: null,
    framework: "custom-python",
    status: "registered",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  fetchAgentsMock.mockReset();
  searchParamsValue = new URLSearchParams();
});

describe("AgentsPage", () => {
  it("renders a link to register a new agent", () => {
    fetchAgentsMock.mockReturnValue(new Promise(() => {}));
    render(<AgentsPage />);

    expect(screen.getByRole("link", { name: /register agent/i })).toHaveAttribute(
      "href",
      "/agents/new"
    );
  });

  it("shows a loading state before data arrives", () => {
    fetchAgentsMock.mockReturnValue(new Promise(() => {}));
    render(<AgentsPage />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders the agent list once loaded", async () => {
    fetchAgentsMock.mockResolvedValue([
      makeAgent({ id: "a1", name: "Support Agent" }),
      makeAgent({ id: "a2", name: "Billing Agent" }),
    ]);

    render(<AgentsPage />);

    await waitFor(() => expect(screen.getByText("Support Agent")).toBeInTheDocument());
    expect(screen.getByText("Billing Agent")).toBeInTheDocument();
  });

  it("shows an empty state when there are no agents", async () => {
    fetchAgentsMock.mockResolvedValue([]);

    render(<AgentsPage />);

    await waitFor(() => expect(screen.getByText("No agents found")).toBeInTheDocument());
  });

  it("shows an error state when the request fails", async () => {
    fetchAgentsMock.mockRejectedValue(new ApiClientError(500, "Backend unavailable"));

    render(<AgentsPage />);

    await waitFor(() => expect(screen.getByText("Backend unavailable")).toBeInTheDocument());
  });

  it("filters the currently-loaded page by name as the user types", async () => {
    fetchAgentsMock.mockResolvedValue([
      makeAgent({ id: "a1", name: "Support Agent" }),
      makeAgent({ id: "a2", name: "Billing Agent" }),
    ]);

    render(<AgentsPage />);
    await waitFor(() => expect(screen.getByText("Support Agent")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("Search this page…"), {
      target: { value: "billing" },
    });

    expect(screen.queryByText("Support Agent")).not.toBeInTheDocument();
    expect(screen.getByText("Billing Agent")).toBeInTheDocument();
  });

  it("passes the environment_id from the URL through to the fetch call", async () => {
    searchParamsValue = new URLSearchParams({ environment_id: "env-42" });
    fetchAgentsMock.mockResolvedValue([]);

    render(<AgentsPage />);

    await waitFor(() =>
      expect(fetchAgentsMock).toHaveBeenCalledWith(
        expect.objectContaining({ environment_id: "env-42" })
      )
    );
  });
});
