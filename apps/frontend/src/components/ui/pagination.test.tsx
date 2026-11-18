import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import Pagination from "./pagination";

describe("Pagination", () => {
  it("disables Previous on the first page", () => {
    render(<Pagination offset={0} limit={25} total={100} onPageChange={vi.fn()} />);
    expect(screen.getByLabelText("Previous page")).toBeDisabled();
  });

  it("disables Next on the last page when total is known", () => {
    render(<Pagination offset={75} limit={25} total={100} onPageChange={vi.fn()} />);
    expect(screen.getByLabelText("Next page")).toBeDisabled();
  });

  it("calls onPageChange with the next offset", () => {
    const onPageChange = vi.fn();
    render(<Pagination offset={0} limit={25} total={100} onPageChange={onPageChange} />);

    fireEvent.click(screen.getByLabelText("Next page"));
    expect(onPageChange).toHaveBeenCalledWith(25);
  });

  it("never lets the offset go negative when going back from the first page", () => {
    const onPageChange = vi.fn();
    render(<Pagination offset={0} limit={25} total={100} onPageChange={onPageChange} />);

    // The button is disabled, but the handler itself should still clamp.
    fireEvent.click(screen.getByLabelText("Previous page"));
    expect(onPageChange).not.toHaveBeenCalled();
  });

  it("keeps Next enabled when total is unknown (bare-list endpoints)", () => {
    render(<Pagination offset={0} limit={25} total={null} onPageChange={vi.fn()} />);
    expect(screen.getByLabelText("Next page")).not.toBeDisabled();
  });
});
