import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AIUsage } from "@/components/ai-usage";
import { PriorityBadge } from "@/components/priority-badge";
import { ProgressBar, ProgressSummary } from "@/components/progress-bar";
import type { AIStatus, Progress } from "@/lib/types";

describe("PriorityBadge", () => {
  it("shows the level and rounded score", () => {
    render(<PriorityBadge level="high" score={61.4} />);
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText("61")).toBeInTheDocument();
  });
  it("omits the score when none is given and flags manual overrides", () => {
    const { rerender } = render(<PriorityBadge level="low" />);
    expect(screen.queryByText(/\d/)).not.toBeInTheDocument();
    rerender(<PriorityBadge level="critical" score={92} manual />);
    expect(screen.getByLabelText("set manually")).toBeInTheDocument();
  });
});

describe("ProgressBar", () => {
  it("exposes its value to assistive technology", () => {
    render(<ProgressBar percent={42.4} label="Project progress" />);
    const bar = screen.getByRole("progressbar", { name: "Project progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "42");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });
});

describe("ProgressSummary", () => {
  const base: Progress = { percent: 20, total_minutes: 300, done_minutes: 60, remaining_minutes: 240, tasks_total: 4, tasks_done: 1, unestimated_tasks: 0 };
  it("summarises tasks and remaining effort", () => {
    render(<ProgressSummary progress={base} />);
    expect(screen.getByText(/1\/4 tasks/)).toBeInTheDocument();
    expect(screen.getByText(/4h left/)).toBeInTheDocument();
  });
  it("is honest about tasks without an estimate", () => {
    render(<ProgressSummary progress={{ ...base, unestimated_tasks: 2 }} />);
    expect(screen.getByText(/2 unestimated/)).toBeInTheDocument();
  });
});

describe("AIUsage", () => {
  const status: AIStatus = {
    configured: true, model: "m", complex_model: "m", requests_today: 3, request_limit: 30, tokens_today: 1200,
    token_limit: 200000, cost_today_usd: 0, cached_today: 2, cost_tracking: false,
  };
  it("renders nothing until the status has loaded", () => {
    const { container } = render(<AIUsage status={null} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("explains that the rest of the app still works when AI is off", () => {
    render(<AIUsage status={{ ...status, configured: false }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/work without it/);
  });
  it("shows allowance used, cache savings, and never a made-up cost", () => {
    render(<AIUsage status={status} />);
    expect(screen.getByText(/3 of 30 requests/)).toBeInTheDocument();
    expect(screen.getByText(/cost tracking off/)).toBeInTheDocument();
    expect(screen.getByText(/2 answered from cache, free/)).toBeInTheDocument();
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  });
  it("shows an estimated cost only when pricing is configured", () => {
    render(<AIUsage status={{ ...status, cost_tracking: true, cost_today_usd: 0.0123 }} />);
    expect(screen.getByText(/about \$0\.0123/)).toBeInTheDocument();
  });
});
