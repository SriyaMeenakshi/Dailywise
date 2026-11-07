import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskRow } from "@/components/task-row";
import type { Task } from "@/lib/types";

const workspace = {
  categories: [{ id: "c1", name: "Academic", color: "#4F6D8F", sort_order: 0 }],
  projects: [{ id: "p1", name: "Capstone" }],
  toggleComplete: vi.fn(),
  openEditor: vi.fn(),
  updateTask: vi.fn(),
  deleteTask: vi.fn(),
};
vi.mock("@/components/workspace-provider", () => ({ useWorkspace: () => workspace }));

const task = (over: Partial<Task> = {}): Task =>
  ({
    id: "t1", title: "Write report", status: "not_started", category_id: "c1", project_id: null, deadline: null,
    estimated_minutes: 90, importance: 3, urgency: 3, priority_level: "medium", priority_score: 40,
    priority_override: null, waiting_on_count: 0, ...over,
  }) as Task;

beforeEach(() => vi.clearAllMocks());

describe("TaskRow", () => {
  it("shows the title as a link to the task page, with category and estimate", () => {
    render(<ul><TaskRow task={task()} /></ul>);
    expect(screen.getByRole("link", { name: /Write report/ })).toHaveAttribute("href", "/tasks/t1");
    expect(screen.getByText("Academic")).toBeInTheDocument();
    expect(screen.getByText("1h 30m")).toBeInTheDocument();
  });

  it("marks overdue work clearly", () => {
    render(<ul><TaskRow task={task({ deadline: "2020-01-01T10:00:00Z" })} /></ul>);
    expect(screen.getByText(/Overdue/)).toBeInTheDocument();
  });

  it("does not call finished work overdue and strikes the title", () => {
    render(<ul><TaskRow task={task({ status: "completed", deadline: "2020-01-01T10:00:00Z" })} /></ul>);
    expect(screen.queryByText(/Overdue/)).not.toBeInTheDocument();
    expect(screen.getByText("Write report")).toHaveClass("line-through");
  });

  it("surfaces only high and critical priorities, and what a task is waiting on", () => {
    const { rerender } = render(<ul><TaskRow task={task()} /></ul>);
    expect(screen.queryByText("medium")).not.toBeInTheDocument();
    rerender(<ul><TaskRow task={task({ priority_level: "critical", priority_score: 91, waiting_on_count: 2 })} /></ul>);
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(screen.getByText(/Waiting on 2/)).toBeInTheDocument();
  });

  it("completes a task from the keyboard-reachable checkbox", async () => {
    render(<ul><TaskRow task={task()} /></ul>);
    await userEvent.click(screen.getByRole("checkbox", { name: /Mark "Write report" as done/ }));
    expect(workspace.toggleComplete).toHaveBeenCalledTimes(1);
  });

  it("disables completion for archived tasks", () => {
    render(<ul><TaskRow task={task({ status: "archived" })} /></ul>);
    expect(screen.getByRole("checkbox")).toHaveAttribute("aria-disabled", "true");
  });

  it("hides the project label in compact mode (the page already names it)", () => {
    const withProject = task({ project_id: "p1" });
    const { rerender } = render(<ul><TaskRow task={withProject} /></ul>);
    expect(screen.getByText("Capstone")).toBeInTheDocument();
    rerender(<ul><TaskRow task={withProject} compact /></ul>);
    expect(screen.queryByText("Capstone")).not.toBeInTheDocument();
  });
});
