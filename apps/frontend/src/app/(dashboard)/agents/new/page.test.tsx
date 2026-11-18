import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import NewAgentPage from "./page";
import { ApiClientError } from "@/lib/api/client";
import type { EnvironmentResponse } from "@/lib/types";

const pushMock = vi.fn();
const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: refreshMock }),
}));

const fetchEnvironmentsMock = vi.fn();
const createAgentMock = vi.fn();

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    fetchEnvironments: (...args: unknown[]) => fetchEnvironmentsMock(...args),
    createAgent: (...args: unknown[]) => createAgentMock(...args),
  };
});

function makeEnvironment(overrides: Partial<EnvironmentResponse> = {}): EnvironmentResponse {
  return {
    id: "env-1",
    project_id: "project-1",
    name: "Production",
    slug: "production",
    description: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  pushMock.mockClear();
  refreshMock.mockClear();
  fetchEnvironmentsMock.mockReset();
  createAgentMock.mockReset();
});

describe("NewAgentPage", () => {
  it("loads environments and preselects the first one", async () => {
    fetchEnvironmentsMock.mockResolvedValue([
      makeEnvironment({ id: "env-1", name: "Production" }),
      makeEnvironment({ id: "env-2", name: "Staging" }),
    ]);

    render(<NewAgentPage />);

    await waitFor(() => expect(screen.getByLabelText("Environment")).toBeInTheDocument());
    expect(screen.getByRole("option", { name: "Production (production)" })).toBeInTheDocument();
  });

  it("registers the agent with an auto-derived slug and navigates to its detail page", async () => {
    fetchEnvironmentsMock.mockResolvedValue([makeEnvironment()]);
    createAgentMock.mockResolvedValue({ id: "new-agent-1" });

    render(<NewAgentPage />);
    await waitFor(() => expect(screen.getByLabelText("Environment")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Support Bot" } });
    fireEvent.click(screen.getByRole("button", { name: "Register agent" }));

    await waitFor(() =>
      expect(createAgentMock).toHaveBeenCalledWith({
        environmentId: "env-1",
        name: "Support Bot",
        slug: "support-bot",
        framework: undefined,
        description: undefined,
      })
    );
    expect(pushMock).toHaveBeenCalledWith("/agents/new-agent-1");
  });

  it("shows a duplicate-name error on HTTP 409, without navigating", async () => {
    fetchEnvironmentsMock.mockResolvedValue([makeEnvironment()]);
    createAgentMock.mockRejectedValue(new ApiClientError(409, "conflict"));

    render(<NewAgentPage />);
    await waitFor(() => expect(screen.getByLabelText("Environment")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Support Bot" } });
    fireEvent.click(screen.getByRole("button", { name: "Register agent" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/already exists in this environment/i)
    );
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("requires a name before submitting", async () => {
    fetchEnvironmentsMock.mockResolvedValue([makeEnvironment()]);

    render(<NewAgentPage />);
    await waitFor(() => expect(screen.getByLabelText("Environment")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Register agent" }));

    expect(screen.getByText("Name is required.")).toBeInTheDocument();
    expect(createAgentMock).not.toHaveBeenCalled();
  });

  it("disables submission and prompts to create an environment first when none exist", async () => {
    fetchEnvironmentsMock.mockResolvedValue([]);

    render(<NewAgentPage />);

    await waitFor(() => expect(screen.getByText(/create one first/i)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Register agent" })).toBeDisabled();
  });
});
