import { describe, expect, it } from "vitest";

import { formatDuration, formatPercent, formatTokenCount } from "./format";

describe("formatDuration", () => {
  it("formats sub-second durations in milliseconds", () => {
    expect(formatDuration(500)).toBe("500ms");
  });

  it("formats durations under a minute in seconds", () => {
    expect(formatDuration(1500)).toBe("1.5s");
  });

  it("formats durations over a minute as minutes and seconds", () => {
    expect(formatDuration(65000)).toBe("1m 5s");
  });

  it("renders an em dash for a missing duration, not 0ms", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(undefined)).toBe("—");
  });
});

describe("formatTokenCount", () => {
  it("distinguishes an unavailable count from a genuine zero", () => {
    expect(formatTokenCount(null)).toBe("Unavailable");
    expect(formatTokenCount(0)).toBe("0");
  });
});

describe("formatPercent", () => {
  it("distinguishes an unavailable rate from a genuine 0%", () => {
    expect(formatPercent(null)).toBe("Unavailable");
    expect(formatPercent(0)).toBe("0%");
    expect(formatPercent(0.666)).toBe("67%");
  });
});
