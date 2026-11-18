import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import OnboardingWizard from "./onboarding-wizard";

const pushMock = vi.fn();
const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: refreshMock }),
}));

const createProjectMock = vi.fn();
const createEnvironmentMock = vi.fn();
const fetchIntegrationApiKeysMock = vi.fn();

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    createProject: (...args: unknown[]) => createProjectMock(...args),
    createEnvironment: (...args: unknown[]) => createEnvironmentMock(...args),
    fetchIntegrationApiKeys: (...args: unknown[]) => fetchIntegrationApiKeysMock(...args),
  };
});

beforeEach(() => {
  pushMock.mockClear();
  refreshMock.mockClear();
  createProjectMock.mockReset();
  createEnvironmentMock.mockReset();
  fetchIntegrationApiKeysMock.mockReset();
  fetchIntegrationApiKeysMock.mockResolvedValue([]);
});

describe("OnboardingWizard", () => {
  it("walks through project -> environment -> integration key in order", async () => {
    createProjectMock.mockResolvedValue({
      id: "project-1",
      organization_id: "org-1",
      name: "Default",
      slug: "default",
      created_at: "2026-01-01T00:00:00Z",
    });
    createEnvironmentMock.mockResolvedValue({
      id: "env-1",
      project_id: "project-1",
      name: "Production",
      slug: "production",
      description: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });

    render(<OnboardingWizard organizationName="Acme Corp" backendUrl="http://localhost:8010" />);

    // Step 1: project.
    expect(screen.getByText("Create your first project")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(createProjectMock).toHaveBeenCalledWith("Default"));

    // Step 2: environment.
    await waitFor(() =>
      expect(screen.getByText("Create a development environment")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(createEnvironmentMock).toHaveBeenCalledWith({
        projectId: "project-1",
        name: "Production",
        slug: "production",
      })
    );

    // Step 3: integration key (the existing ApiKeysSection, reused as-is).
    await waitFor(() =>
      expect(
        screen.getByText("Generate an integration key for the Python SDK")
      ).toBeInTheDocument()
    );
    expect(screen.getByText("API Keys")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Go to dashboard" }));
    expect(pushMock).toHaveBeenCalledWith("/");
  });
});
