"use client";

import { useMemo } from "react";
import Link from "next/link";
import { QuickAdd } from "@/components/quick-add";
import { TaskRow } from "@/components/task-row";
import { Button } from "@/components/ui/button";
import { EmptyState, ListSkeleton, LoadError } from "@/components/workspace-states";
import { useWorkspace } from "@/components/workspace-provider";
import { byUrgency, daysUntil, greeting, isActive, isDueToday, isOverdue, startOfDay } from "@/lib/task-utils";
import type { Task } from "@/lib/types";

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <section className="space-y-2.5">
      <h2 className="text-section">
        {title}
        {count !== undefined && <span className="ml-2 tabular-nums">{count}</span>}
      </h2>
      <ul className="space-y-2">{children}</ul>
    </section>
  );
}

export default function DashboardPage() {
  const { me, tasks, loading, loadError, openEditor } = useWorkspace();
  const now = new Date();

  const view = useMemo(() => {
    const today = startOfDay(new Date()).getTime();
    const overdue = tasks.filter((t) => isOverdue(t) && !isDueToday(t)).sort(byUrgency);
    const dueToday = tasks.filter((t) => isDueToday(t)).sort(byUrgency);
    const completedToday = tasks.filter((t) => t.completed_at && new Date(t.completed_at).getTime() >= today);
    const shown = new Set([...overdue, ...dueToday].map((t) => t.id));
    const upcoming = tasks
      .filter((t) => isActive(t) && t.deadline && !shown.has(t.id) && daysUntil(t.deadline) > 0 && daysUntil(t.deadline) <= 7)
      .sort(byUrgency);
    upcoming.forEach((t) => shown.add(t.id));
    const important = tasks
      .filter((t) => isActive(t) && !shown.has(t.id) && (t.priority_level === "critical" || t.priority_level === "high"))
      .sort((a, b) => b.priority_score - a.priority_score)
      .slice(0, 5);
    const inboxAll = tasks.filter((t) => t.status === "inbox" && !shown.has(t.id));
    const inbox = inboxAll.slice(0, 5);
    const inboxExtra = inboxAll.length - inbox.length;
    const plannedTotal = dueToday.length + overdue.length + completedToday.length;
    return { overdue, dueToday, completedToday, upcoming, important, inbox, inboxExtra, plannedTotal };
  }, [tasks]);

  const name = me?.display_name?.split(" ")[0] ?? me?.email?.split("@")[0];
  const pct = view.plannedTotal ? Math.round((view.completedToday.length / view.plannedTotal) * 100) : 0;
  const hasAnyActive = tasks.some(isActive);

  return (
    <div className="space-y-8">
      <header className="space-y-1">
        <p className="text-section">{now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</p>
        <h1 className="text-display">
          {greeting(now)}
          {name ? `, ${name}` : ""}.
        </h1>
      </header>

      <QuickAdd />

      <nav aria-label="Shortcuts" className="-mt-4 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        <Link href="/planner" className="font-medium underline underline-offset-4">Plan my day</Link>
        <Link href="/priorities" className="text-muted-foreground hover:text-foreground">See all priorities</Link>
      </nav>

      {loadError ? (
        <LoadError message={loadError} />
      ) : loading ? (
        <ListSkeleton />
      ) : (
        <>
          {view.plannedTotal > 0 && (
            <div className="rounded-2xl border bg-card p-4 shadow-card">
              <div className="flex items-baseline justify-between">
                <p className="text-sm font-medium">Today’s progress</p>
                <p className="text-sm tabular-nums text-muted-foreground">
                  {view.completedToday.length} of {view.plannedTotal} done
                </p>
              </div>
              <div
                className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Tasks completed today"
              >
                <div className="h-full rounded-full bg-sage transition-[width] duration-500" style={{ width: `${pct}%` }} />
              </div>
            </div>
          )}

          {!hasAnyActive && view.completedToday.length === 0 ? (
            <EmptyState
              title="A clear slate"
              body="Capture whatever is on your mind above. You can add deadlines, estimates and detail whenever you’re ready."
              action={<Button onClick={() => openEditor(null)}>Add a task with details</Button>}
            />
          ) : (
            <div className="space-y-8">
              {view.overdue.length > 0 && (
                <Section title="Overdue" count={view.overdue.length}>
                  {view.overdue.map((t: Task) => <TaskRow key={t.id} task={t} />)}
                </Section>
              )}
              <Section title="Due today" count={view.dueToday.length}>
                {view.dueToday.length ? (
                  view.dueToday.map((t) => <TaskRow key={t.id} task={t} />)
                ) : (
                  <li className="rounded-xl border border-dashed px-4 py-5 text-sm text-muted-foreground">
                    Nothing is due today.
                  </li>
                )}
              </Section>
              {view.important.length > 0 && (
                <Section title="High priority" count={view.important.length}>
                  {view.important.map((t) => <TaskRow key={t.id} task={t} />)}
                </Section>
              )}
              {view.upcoming.length > 0 && (
                <Section title="Coming up this week" count={view.upcoming.length}>
                  {view.upcoming.map((t) => <TaskRow key={t.id} task={t} />)}
                </Section>
              )}
              {view.inbox.length > 0 && (
                <div className="space-y-2.5">
                  <Section title="Inbox" count={view.inbox.length + view.inboxExtra}>
                    {view.inbox.map((t) => <TaskRow key={t.id} task={t} />)}
                  </Section>
                  <p className="text-sm text-muted-foreground">
                    Captured but not yet sorted.{" "}
                    <Link href="/tasks?status=inbox" className="font-medium text-foreground underline underline-offset-4">
                      {view.inboxExtra > 0 ? `See all ${view.inbox.length + view.inboxExtra}` : "Open inbox"}
                    </Link>
                  </p>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
