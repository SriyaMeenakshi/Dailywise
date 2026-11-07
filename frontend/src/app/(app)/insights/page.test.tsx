import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InsightsPage from "@/app/(app)/insights/page";
import type { Analytics } from "@/lib/types";

const analytics = vi.fn();
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api: { insights: { analytics: (...a: unknown[]) => analytics(...a) } } }));
vi.mock("@/components/workspace-provider", () => ({ useWorkspace: () => ({ tasks: [] }) }));

const data = (over: Partial<Analytics> = {}): Analytics => ({
  days: 7, completed: 4, pending: 3, overdue: 1, blocked: 1, completed_with_deadline: 2, completed_on_time: 1,
  daily: Array.from({ length: 7 }, (_, i) => ({ date: `2026-11-0${i + 1}`, completed: i === 6 ? 3 : 0, completed_minutes: i === 6 ? 225 : 0 })),
  by_category: [{ name: "Academic", color: "#4F6D8F", completed: 2, pending: 1 }],
  time_accuracy: { tasks: 3, estimated_minutes: 180, actual_minutes: 200, biggest_misses: [{ id: "t1", title: "Write DBMS report", deadline: null, estimated_minutes: 90, actual_minutes: 120, priority_level: null }] },
  projects: [{ id: "p1", name: "Capstone", percent: 20, remaining_minutes: 240, deadline: null }],
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  analytics.mockResolvedValue(data());
});

describe("Insights page", () => {
  it("shows real numbers from the API, including an honest on-time rate", async () => {
    render(<InsightsPage />);
    const summary = await screen.findByRole("region", { name: "Summary" });
    expect(summary).toHaveTextContent("Done · 7d");
    expect(summary).toHaveTextContent("50%");
    expect(summary).toHaveTextContent("1 of 2 with deadlines");
    expect(screen.getByText("1 blocked")).toBeInTheDocument();
  });

  it("describes estimate accuracy in plain words", async () => {
    render(<InsightsPage />);
    const section = await screen.findByRole("region", { name: "Estimated versus actual time" });
    expect(section).toHaveTextContent("estimated 3h and spent 3h 20m (20m over)");
    expect(section).toHaveTextContent("Write DBMS report");
  });

  it("gives screen readers the chart data as a table", async () => {
    render(<InsightsPage />);
    const table = await screen.findByRole("table", { name: "Tasks completed per day" });
    expect(table.querySelectorAll("tbody tr")).toHaveLength(7);
  });

  it("lists category and project progress with accessible bars", async () => {
    render(<InsightsPage />);
    expect(await screen.findByRole("progressbar", { name: "Academic: 2 of 3 done" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Capstone progress" })).toHaveAttribute("aria-valuenow", "20");
  });

  it("requests the chosen period and the user's timezone offset", async () => {
    render(<InsightsPage />);
    await screen.findByRole("region", { name: "Summary" });
    expect(analytics).toHaveBeenLastCalledWith(7, expect.any(Number));
    await userEvent.click(screen.getByRole("button", { name: "30 days" }));
    await waitFor(() => expect(analytics).toHaveBeenLastCalledWith(30, expect.any(Number)));
  });

  it("shows an empty state instead of empty charts for a new account", async () => {
    analytics.mockResolvedValue(data({ completed: 0, pending: 0, by_category: [], projects: [] }));
    render(<InsightsPage />);
    expect(await screen.findByText("Nothing to chart yet")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("explains how to get estimate insights when no task has both numbers", async () => {
    analytics.mockResolvedValue(data({ time_accuracy: { tasks: 0, estimated_minutes: 0, actual_minutes: 0, biggest_misses: [] } }));
    render(<InsightsPage />);
    expect(await screen.findByText(/Add an estimate/)).toBeInTheDocument();
  });

  it("shows a recoverable error when loading fails", async () => {
    const { ApiError } = await import("@/lib/api");
    analytics.mockRejectedValue(new ApiError("Server is down", 500));
    render(<InsightsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Server is down");
  });
});
