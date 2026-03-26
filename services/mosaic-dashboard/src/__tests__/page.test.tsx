// @vitest-environment jsdom
import { expect, test, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import Page from "../app/page";

// Mock all panel components to isolate page layout tests
vi.mock("@/components/ModePanel", () => ({ default: () => <div data-testid="mode-panel" /> }));
vi.mock("@/components/UsageCounter", () => ({ default: () => <div data-testid="usage-counter" /> }));
vi.mock("@/components/FestivalPanel", () => ({ default: () => <div data-testid="festival-panel" /> }));
vi.mock("@/components/SimulationPanel", () => ({ default: () => <div data-testid="simulation-panel" /> }));
vi.mock("@/components/AtlasClusters", () => ({ default: () => <div data-testid="atlas-clusters" /> }));

afterEach(cleanup);

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

test("renders Mosaic Dashboard heading", () => {
  render(<Page />);
  expect(
    screen.getByRole("heading", { level: 1, name: "Mosaic Dashboard" }),
  ).toBeDefined();
});

test("renders all 5 panels", () => {
  render(<Page />);
  expect(screen.getByTestId("mode-panel")).toBeDefined();
  expect(screen.getByTestId("usage-counter")).toBeDefined();
  expect(screen.getByTestId("festival-panel")).toBeDefined();
  expect(screen.getByTestId("simulation-panel")).toBeDefined();
  expect(screen.getByTestId("atlas-clusters")).toBeDefined();
});
