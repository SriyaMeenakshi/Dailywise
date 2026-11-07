import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReflectPage from "@/app/(app)/reflect/page";
import type { Review } from "@/lib/types";

const review = vi.fn();
const saveReview = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  api: { insights: { review: (...a: unknown[]) => review(...a), saveReview: (...a: unknown[]) => saveReview(...a) } },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const brief = (id: string, title: string) => ({ id, title, deadline: null, estimated_minutes: null, actual_minutes: null, priority_level: null });
const base = (over: Partial<Review> = {}): Review => ({
  date: "2026-11-06",
  saved: null,
  facts: {
    completed: [brief("1", "Write DBMS report"), brief("2", "Read NLP paper")],
    completed_minutes: 165,
    remaining: [brief("3", "Overdue essay")],
    blocked: [brief("4", "Waiting on prof reply")],
    suggested_tomorrow: [brief("5", "Build API"), brief("6", "Plan sprint")],
  },
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  review.mockResolvedValue(base());
  saveReview.mockImplementation(async (_d: string, _o: number, text: NonNullable<Review["saved"]>) => base({ saved: text }));
});

describe("End-of-day review", () => {
  it("shows facts from the tasks and the four reflection questions", async () => {
    render(<ReflectPage />);
    const completed = await screen.findByRole("region", { name: "Completed" });
    expect(completed).toHaveTextContent("Write DBMS report");
    expect(completed).toHaveTextContent("About 2h 45m of work");
    expect(screen.getByRole("region", { name: "Blocked" })).toHaveTextContent("Waiting on prof reply");
    for (const q of ["What did I accomplish?", "What remains?", "What blocked me?", "What should I prioritise tomorrow?"]) {
      expect(screen.getByLabelText(q)).toBeInTheDocument();
    }
  });

  it("fills only empty answers from real data and never overwrites what you wrote", async () => {
    render(<ReflectPage />);
    await screen.findByRole("region", { name: "Completed" });
    await userEvent.type(screen.getByLabelText("What blocked me?"), "My own words");
    await userEvent.click(screen.getByRole("button", { name: /Fill from my tasks/ }));
    expect(screen.getByLabelText("What did I accomplish?")).toHaveValue("• Write DBMS report\n• Read NLP paper");
    expect(screen.getByLabelText("What blocked me?")).toHaveValue("My own words");
    expect(screen.getByLabelText("What should I prioritise tomorrow?")).toHaveValue("• Build API\n• Plan sprint");
  });

  it("saves the reflection and confirms it", async () => {
    render(<ReflectPage />);
    await screen.findByRole("region", { name: "Completed" });
    const save = screen.getByRole("button", { name: "Save review" });
    expect(save).toBeDisabled(); // nothing to save yet
    await userEvent.type(screen.getByLabelText("What did I accomplish?"), "Shipped it");
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    await userEvent.click(save);
    await waitFor(() => expect(saveReview).toHaveBeenCalledTimes(1));
    expect(saveReview.mock.calls[0][2]).toMatchObject({ accomplished: "Shipped it", remaining: "", blockers: "", tomorrow_focus: "" });
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });

  it("loads a previously saved reflection", async () => {
    review.mockResolvedValue(base({ saved: { accomplished: "Done", remaining: "", blockers: "", tomorrow_focus: "Tests" } }));
    render(<ReflectPage />);
    await screen.findByRole("region", { name: "Completed" });
    expect(screen.getByLabelText("What did I accomplish?")).toHaveValue("Done");
    expect(screen.getByLabelText("What should I prioritise tomorrow?")).toHaveValue("Tests");
  });

  it("asks before leaving the day with unsaved changes", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<ReflectPage />);
    await screen.findByRole("region", { name: "Completed" });
    await userEvent.type(screen.getByLabelText("What remains?"), "Unfinished");
    await userEvent.click(screen.getByRole("button", { name: "Previous day" }));
    expect(confirm).toHaveBeenCalled();
    expect(review).toHaveBeenCalledTimes(1); // stayed on the same day
    confirm.mockRestore();
  });

  it("cannot move into the future", async () => {
    render(<ReflectPage />);
    await screen.findByRole("region", { name: "Completed" });
    expect(screen.getByRole("button", { name: "Next day" })).toBeDisabled();
  });

  it("shows a quiet day without inventing activity", async () => {
    review.mockResolvedValue(base({ facts: { completed: [], completed_minutes: 0, remaining: [], blocked: [], suggested_tomorrow: [] } }));
    render(<ReflectPage />);
    expect(await screen.findByText("Nothing completed this day.")).toBeInTheDocument();
    expect(screen.getByText("No open tasks.")).toBeInTheDocument();
  });
});
