import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import LoginPage from "./page";
import { ApiClientError } from "@/lib/api/client";

const pushMock = vi.fn();
const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: refreshMock }),
}));

const loginMock = vi.fn();

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return { ...actual, login: (...args: unknown[]) => loginMock(...args) };
});

beforeEach(() => {
  pushMock.mockClear();
  refreshMock.mockClear();
  loginMock.mockReset();
});

describe("LoginPage", () => {
  it("renders email and password fields and a submit button", () => {
    render(<LoginPage />);

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("navigates to the dashboard on a successful login", async () => {
    loginMock.mockResolvedValue({ user: { id: "1", email: "admin@example.com" } });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "admin@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/"));
    expect(loginMock).toHaveBeenCalledWith("admin@example.com", "correct-password");
  });

  it("shows a generic error message on invalid credentials, without navigating", async () => {
    loginMock.mockRejectedValue(new ApiClientError(401, "Invalid email or password"));

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "admin@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Invalid email or password."));
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("shows a rate-limit-specific message on HTTP 429", async () => {
    loginMock.mockRejectedValue(new ApiClientError(429, "Too many login attempts"));

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "admin@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "whatever" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/too many login attempts/i)
    );
  });
});
