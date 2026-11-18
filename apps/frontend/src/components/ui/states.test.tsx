import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { EmptyState, ErrorState, LoadingSkeleton } from "./states";

describe("LoadingSkeleton", () => {
  it("renders a status role so loading is announced accessibly", () => {
    render(<LoadingSkeleton rows={3} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("renders the title and optional description", () => {
    render(<EmptyState title="No agents found" description="Register one to see it here." />);
    expect(screen.getByText("No agents found")).toBeInTheDocument();
    expect(screen.getByText("Register one to see it here.")).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("renders the error message and calls onRetry when clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Backend returned HTTP 500" onRetry={onRetry} />);

    expect(screen.getByText("Backend returned HTTP 500")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not render a retry button when onRetry is not given", () => {
    render(<ErrorState message="Backend returned HTTP 500" />);
    expect(screen.queryByText("Retry")).not.toBeInTheDocument();
  });
});
