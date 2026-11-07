import { describe, expect, it } from "vitest";
import { byUrgency, daysUntil, formatDeadline, formatMinutes, fromLocalInput, greeting, isDueToday, isOverdue, toLocalInput } from "@/lib/task-utils";
import type { Task } from "@/lib/types";

const NOW = new Date(2026, 10, 6, 10, 0, 0); // 6 Nov 2026, 10:00 local

const make = (over: Partial<Task> = {}): Task =>
  ({
    id: "1", title: "t", status: "not_started", deadline: null, importance: 3, urgency: 3,
    estimated_minutes: null, ...over,
  }) as Task;

const at = (d: Date) => d.toISOString();

describe("formatMinutes", () => {
  it.each([[5, "5m"], [60, "1h"], [90, "1h 30m"], [125, "2h 5m"]])("%i -> %s", (m, out) => expect(formatMinutes(m)).toBe(out));
});

describe("daysUntil / formatDeadline", () => {
  it("counts whole calendar days", () => {
    expect(daysUntil(at(new Date(2026, 10, 6, 23, 59)), NOW)).toBe(0);
    expect(daysUntil(at(new Date(2026, 10, 7, 0, 5)), NOW)).toBe(1);
    expect(daysUntil(at(new Date(2026, 10, 5, 23, 0)), NOW)).toBe(-1);
  });
  it("uses friendly words near today and dates further out", () => {
    expect(formatDeadline(at(new Date(2026, 10, 6)), NOW)).toBe("Today");
    expect(formatDeadline(at(new Date(2026, 10, 7)), NOW)).toBe("Tomorrow");
    expect(formatDeadline(at(new Date(2026, 10, 5)), NOW)).toBe("Yesterday");
    expect(formatDeadline(at(new Date(2026, 10, 7, 15, 30)), NOW)).toMatch(/^Tomorrow, 3:30/);
    expect(formatDeadline(at(new Date(2027, 0, 20)), NOW)).toMatch(/20/);
  });
});

describe("isOverdue / isDueToday", () => {
  it("flags unfinished tasks past their deadline", () => {
    expect(isOverdue(make({ deadline: at(new Date(2026, 10, 6, 9, 0)) }), NOW)).toBe(true);
    expect(isOverdue(make({ deadline: at(new Date(2026, 10, 6, 11, 0)) }), NOW)).toBe(false);
  });
  it("never flags finished or archived tasks, or tasks with no deadline", () => {
    const past = at(new Date(2020, 0, 1));
    expect(isOverdue(make({ status: "completed", deadline: past }), NOW)).toBe(false);
    expect(isOverdue(make({ status: "archived", deadline: past }), NOW)).toBe(false);
    expect(isOverdue(make(), NOW)).toBe(false);
  });
  it("detects tasks due today", () => {
    expect(isDueToday(make({ deadline: at(new Date(2026, 10, 6, 20, 0)) }), NOW)).toBe(true);
    expect(isDueToday(make({ deadline: at(new Date(2026, 10, 7, 20, 0)) }), NOW)).toBe(false);
  });
});

describe("local datetime inputs", () => {
  it("round-trips a value through ISO without shifting the time", () => {
    const local = "2026-11-20T17:00";
    expect(toLocalInput(fromLocalInput(local))).toBe(local);
  });
  it("handles empty values", () => {
    expect(toLocalInput(null)).toBe("");
    expect(fromLocalInput("")).toBeNull();
  });
});

describe("greeting", () => {
  it.each([[3, "Still up"], [9, "Good morning"], [14, "Good afternoon"], [20, "Good evening"]])("%ih -> %s", (h, out) => {
    expect(greeting(new Date(2026, 10, 6, h))).toBe(out);
  });
});

describe("byUrgency", () => {
  it("sorts by deadline with undated tasks last, then by weight", () => {
    const a = make({ id: "a", deadline: at(new Date(2026, 10, 9)) });
    const b = make({ id: "b", deadline: at(new Date(2026, 10, 8)) });
    const c = make({ id: "c" });
    const d = make({ id: "d", importance: 5, urgency: 5 });
    expect([a, c, b, d].sort(byUrgency).map((t) => t.id)).toEqual(["b", "a", "d", "c"]);
  });
});
