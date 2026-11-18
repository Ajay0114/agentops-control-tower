import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import SignupPage from "./page";
import { ApiClientError } from "@/lib/api/client";

const pushMock = vi.fn();
const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: refreshMock }),
}));

const signupMock = vi.fn();

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return { ...actual, signup: (...args: unknown[]) => signupMock(...args) };
});

beforeEach(() => {
  pushMock.mockClear();
  refreshMock.mockClear();
  signupMock.mockReset();
});

describe("SignupPage", () => {
  it("renders organization name, email, password fields and a submit button", () => {
    render(<SignupPage />);

    expect(screen.getByLabelText("Organization name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  });

  it("creates the account and navigates to onboarding on success", async () => {
    signupMock.mockResolvedValue({ user: { id: "1", email: "founder@acme.test" } });

    render(<SignupPage />);

    fireEvent.change(screen.getByLabelText("Organization name"), {
      target: { value: "Acme Corp" },
    });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "founder@acme.test" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "x12345678" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/onboarding"));
    expect(signupMock).toHaveBeenCalledWith("Acme Corp", "founder@acme.test", "x12345678");
  });

  it("shows a duplicate-email message on HTTP 409, without navigating", async () => {
    signupMock.mockRejectedValue(new ApiClientError(409, "An account with this email already exists"));

    render(<SignupPage />);

    fireEvent.change(screen.getByLabelText("Organization name"), { target: { value: "Acme" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "dup@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "x12345678" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/already exists/i)
    );
    expect(pushMock).not.toHaveBeenCalled();
  });
});
