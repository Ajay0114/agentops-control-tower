import { act, render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";

/**
 * For components that call React's `use()` on a Promise prop (every dynamic
 * route page here, via `use(params)`): even an already-resolved promise
 * still suspends for one microtask tick, which RTL's plain `render()` does
 * not wait for on its own, producing an "update not wrapped in act" warning
 * and a DOM that never reflects the resolved state. This flushes that tick.
 */
export async function renderAsync(ui: ReactElement): Promise<RenderResult> {
  let result: RenderResult;

  await act(async () => {
    result = render(ui);
  });

  return result!;
}
