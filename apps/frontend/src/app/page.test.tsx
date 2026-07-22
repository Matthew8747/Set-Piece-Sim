import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import Home from "./page";

test("landing page renders the product name", () => {
  render(<Home />);
  expect(screen.getByRole("heading", { level: 1, name: "Restart Lab" })).toBeDefined();
});

test("landing page does not leak a build-environment badge into the UI", () => {
  render(<Home />);
  // The badge was hardcoded to "dev", so production shipped a DEV chip.
  expect(screen.queryByText("dev")).toBeNull();
});
