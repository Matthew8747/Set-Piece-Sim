import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ReplayPlayer } from "./ReplayPlayer";

afterEach(() => {
  vi.restoreAllMocks();
});

function renderPlayer(props?: Partial<Parameters<typeof ReplayPlayer>[0]>) {
  const onFrame = vi.fn();
  render(
    <ReplayPlayer frameCount={5} times={[0, 0.1, 0.2, 0.3, 0.4]} onFrame={onFrame} {...props}>
      {(frame) => <span data-testid="frame">{frame}</span>}
    </ReplayPlayer>,
  );
  return { onFrame };
}

test("renders children at the initial frame and a play control", () => {
  renderPlayer();
  expect(screen.getByTestId("frame").textContent).toBe("0");
  expect(screen.getByRole("button", { name: /play/i })).toBeDefined();
});

test("ArrowRight scrubs forward and emits onFrame", () => {
  const { onFrame } = renderPlayer();
  const group = screen.getByRole("group", { name: /replay/i });
  fireEvent.keyDown(group, { key: "ArrowRight" });
  expect(screen.getByTestId("frame").textContent).toBe("1");
  expect(onFrame).toHaveBeenCalledWith(1);
});

test("ArrowLeft clamps at zero", () => {
  renderPlayer();
  const group = screen.getByRole("group", { name: /replay/i });
  fireEvent.keyDown(group, { key: "ArrowLeft" });
  expect(screen.getByTestId("frame").textContent).toBe("0");
});

test("renders event markers that seek to the nearest frame", () => {
  renderPlayer({ events: [{ time_s: 0.2, kind: "shot" }] });
  const marker = screen.getByRole("button", { name: /shot/i });
  fireEvent.click(marker);
  // 0.2 s is the third sample (index 2).
  expect(screen.getByTestId("frame").textContent).toBe("2");
});

test("reduced motion hides auto-play and offers step controls", () => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
  renderPlayer();
  expect(screen.queryByRole("button", { name: /play/i })).toBeNull();
  expect(screen.getByRole("button", { name: /step forward/i })).toBeDefined();
});
