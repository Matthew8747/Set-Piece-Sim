import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import Home from "./page";

test("landing page renders the product name", () => {
  render(<Home />);
  expect(screen.getByRole("heading", { level: 1, name: "Restart Lab" })).toBeDefined();
});

test("landing page shows the environment badge from shared types", () => {
  render(<Home />);
  expect(screen.getByText("dev")).toBeDefined();
});
