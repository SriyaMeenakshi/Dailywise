import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuickAdd } from "@/components/quick-add";

const workspace = { addTask: vi.fn(), openEditor: vi.fn() };
vi.mock("@/components/workspace-provider", () => ({ useWorkspace: () => workspace }));

beforeEach(() => {
  vi.clearAllMocks();
  workspace.addTask.mockResolvedValue({ id: "new" });
});

describe("QuickAdd", () => {
  it("captures a trimmed title on Enter and clears the field", async () => {
    render(<QuickAdd />);
    const input = screen.getByLabelText("Task title");
    await userEvent.type(input, "  Buy notebook  {Enter}");
    expect(workspace.addTask).toHaveBeenCalledWith({ title: "Buy notebook" });
    expect(input).toHaveValue("");
  });

  it("ignores blank input", async () => {
    render(<QuickAdd />);
    await userEvent.type(screen.getByLabelText("Task title"), "   {Enter}");
    expect(workspace.addTask).not.toHaveBeenCalled();
  });

  it("keeps what you typed if saving fails, so nothing is lost", async () => {
    workspace.addTask.mockResolvedValue(null);
    render(<QuickAdd />);
    const input = screen.getByLabelText("Task title");
    await userEvent.type(input, "Important thing{Enter}");
    expect(input).toHaveValue("Important thing");
  });

  it("offers the detailed editor and the AI capture page", async () => {
    render(<QuickAdd />);
    await userEvent.click(screen.getByRole("button", { name: /details/i }));
    expect(workspace.openEditor).toHaveBeenCalledWith(null);
    expect(screen.getByRole("link", { name: /Capture with AI/ })).toHaveAttribute("href", "/capture");
  });
});
