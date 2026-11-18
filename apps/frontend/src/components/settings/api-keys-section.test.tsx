import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import ApiKeysSection from "./api-keys-section";
import { ApiClientError } from "@/lib/api/client";
import type { IntegrationApiKey } from "@/lib/types";

const fetchIntegrationApiKeysMock = vi.fn();
const createIntegrationApiKeyMock = vi.fn();
const revokeIntegrationApiKeyMock = vi.fn();

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    fetchIntegrationApiKeys: (...args: unknown[]) => fetchIntegrationApiKeysMock(...args),
    createIntegrationApiKey: (...args: unknown[]) => createIntegrationApiKeyMock(...args),
    revokeIntegrationApiKey: (...args: unknown[]) => revokeIntegrationApiKeyMock(...args),
  };
});

Object.assign(navigator, {
  clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
});

function makeKey(overrides: Partial<IntegrationApiKey> = {}): IntegrationApiKey {
  return {
    id: "key-1",
    name: "CI key",
    key_prefix: "aops_deadbeef",
    project_id: null,
    environment_id: null,
    status: "active",
    created_at: "2026-01-01T00:00:00Z",
    last_used_at: null,
    revoked_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  fetchIntegrationApiKeysMock.mockReset();
  createIntegrationApiKeyMock.mockReset();
  revokeIntegrationApiKeyMock.mockReset();
});

describe("ApiKeysSection", () => {
  it("renders the existing keys", async () => {
    fetchIntegrationApiKeysMock.mockResolvedValue([makeKey()]);

    render(<ApiKeysSection backendUrl="http://localhost:8010" />);

    await waitFor(() => expect(screen.getByText("CI key")).toBeInTheDocument());
    expect(screen.getByText("aops_deadbeef")).toBeInTheDocument();
  });

  it("shows an empty state when there are no keys yet", async () => {
    fetchIntegrationApiKeysMock.mockResolvedValue([]);

    render(<ApiKeysSection backendUrl="http://localhost:8010" />);

    await waitFor(() => expect(screen.getByText("No integration keys yet")).toBeInTheDocument());
  });

  it("shows the raw key exactly once after creating one, with the onboarding guide available", async () => {
    fetchIntegrationApiKeysMock.mockResolvedValue([]);
    createIntegrationApiKeyMock.mockResolvedValue({
      api_key: makeKey({ id: "key-2", name: "New key" }),
      raw_key: "aops_abc123_rawsecretvalue",
    });

    render(<ApiKeysSection backendUrl="http://localhost:8010" />);
    await waitFor(() => expect(screen.getByText("No integration keys yet")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("New key name"), { target: { value: "New key" } });
    fireEvent.click(screen.getByRole("button", { name: /create key/i }));

    await waitFor(() =>
      expect(screen.getByText("aops_abc123_rawsecretvalue")).toBeInTheDocument()
    );
    expect(createIntegrationApiKeyMock).toHaveBeenCalledWith({ name: "New key" });
    expect(screen.getByText(/copy this key now/i)).toBeInTheDocument();

    // The SDK guide never hardcodes the real key - only a placeholder/env var.
    fireEvent.click(screen.getByText(/how do i use this with the python sdk/i));
    const guideCode = screen.getByText(/pip install agentops-sdk-python/);
    expect(guideCode).toBeInTheDocument();
  });

  it("requires a confirmation click before actually revoking a key", async () => {
    fetchIntegrationApiKeysMock.mockResolvedValue([makeKey()]);
    revokeIntegrationApiKeyMock.mockResolvedValue(makeKey({ status: "revoked" }));

    render(<ApiKeysSection backendUrl="http://localhost:8010" />);
    await waitFor(() => expect(screen.getByText("CI key")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Revoke CI key"));
    expect(revokeIntegrationApiKeyMock).not.toHaveBeenCalled();
    expect(screen.getByText("Revoke this key?")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => expect(revokeIntegrationApiKeyMock).toHaveBeenCalledWith("key-1"));
  });

  it("cancelling the confirmation does not revoke the key", async () => {
    fetchIntegrationApiKeysMock.mockResolvedValue([makeKey()]);

    render(<ApiKeysSection backendUrl="http://localhost:8010" />);
    await waitFor(() => expect(screen.getByText("CI key")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Revoke CI key"));
    fireEvent.click(screen.getByText("Cancel"));

    expect(revokeIntegrationApiKeyMock).not.toHaveBeenCalled();
    expect(screen.queryByText("Revoke this key?")).not.toBeInTheDocument();
  });

  it("does not offer to revoke an already-revoked key", async () => {
    fetchIntegrationApiKeysMock.mockResolvedValue([makeKey({ status: "revoked" })]);

    render(<ApiKeysSection backendUrl="http://localhost:8010" />);
    await waitFor(() => expect(screen.getByText("CI key")).toBeInTheDocument());

    expect(screen.queryByLabelText("Revoke CI key")).not.toBeInTheDocument();
  });

  it("shows an error state when loading keys fails", async () => {
    fetchIntegrationApiKeysMock.mockRejectedValue(new ApiClientError(401, "Unauthorized"));

    render(<ApiKeysSection backendUrl="http://localhost:8010" />);

    await waitFor(() => expect(screen.getByText("Unauthorized")).toBeInTheDocument());
  });
});
