// @vitest-environment jsdom
import { expect, test, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import Page from "../app/page";

afterEach(cleanup);

test("renders Mosaic Dashboard heading", () => {
  render(<Page />);
  expect(
    screen.getByRole("heading", { level: 1, name: "Mosaic Dashboard" }),
  ).toBeDefined();
});

test("shows proxy route for delta-kernel", () => {
  render(<Page />);
  expect(screen.getByText(/\/api\/delta\/\*/)).toBeDefined();
});

test("shows proxy route for MiroFish", () => {
  render(<Page />);
  expect(screen.getByText(/\/api\/mirofish\/\*/)).toBeDefined();
});

test("shows proxy route for orchestrator", () => {
  render(<Page />);
  expect(screen.getByText(/\/api\/mosaic\/\*/)).toBeDefined();
});
