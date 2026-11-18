import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import StatusBadge from "./status-badge";

describe("StatusBadge", () => {
  it("renders the status text", () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("renders an unknown status without crashing, using a default style", () => {
    render(<StatusBadge status="some-unknown-status" />);
    expect(screen.getByText("some-unknown-status")).toBeInTheDocument();
  });
});
