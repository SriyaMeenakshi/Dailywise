"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { NotebookPen } from "lucide-react";
import { cn } from "cn";
import { ProgressBar } from "@/components/progress-bar";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState, ListSkeleton, LoadError } from "@/components/workspace-states";
import { useWorkspace } from "@/components/workspace-provider";
import { api, ApiError } from "@/lib/api";
import { formatDeadline, formatMinutes } from "@/lib/task-utils";
import type { Analytics } from "@/lib/types";

const PERIODS = [7, 30] as const;
const offset = () => -new Date().getTimezoneOffset();
const dayLabel = (iso: string, long = false) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, long ? { weekday: "long", day: "numeric", month: "short" } : { weekday: "short", day: "numeric" });

function Stat({ label, value, hint, tone }: { label: string; value: string | number; hint?: string; tone?: "bad" }) {
  return (
    <div className="rounded-2xl border bg-card p-4 shadow-card">
      <p className="text-section">{label}</p>
      <p className={cn("mt-1 font-display text-3xl tabular-nums", tone === "bad" && Number(value) > 0 && "text-destructive")}>{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default function InsightsPage() {
  const { tasks } = useWorkspace();
  const [days, setDays] = useState<number>(7);
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.insights.analytics(days, offset()));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load your insights");
    }
  }, [days]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reload for the period and when tasks change
    void load();
  }, [load, tasks]);

  const empty = data && data.completed === 0 && data.pending === 0 && data.by_category.length === 0;
  const timeDelta = data ? data.time_accuracy.actual_minutes - data.time_accuracy.estimated_minutes : 0;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-section">Only what you’ve actually done</p>
          <h1 className="text-display mt-1">Insights</h1>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border p-0.5" role="group" aria-label="Time period">
            {PERIODS.map((p) => (
              <button
                key={p}
                type="button"
                aria-pressed={days === p}
                onClick={() => setDays(p)}
                className={cn("rounded-md px-3 py-1 text-sm outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50", days === p ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}
              >
                {p} days
              </button>
            ))}
          </div>
          <Link href="/reflect" className={buttonVariants({ variant: "outline" })}>
            <NotebookPen /> <span className="hidden sm:inline">End-of-day review</span><span className="sm:hidden">Review</span>
          </Link>
        </div>
      </header>

      {error ? (
        <LoadError message={error} />
      ) : !data ? (
        <ListSkeleton rows={4} />
      ) : empty ? (
        <EmptyState title="Nothing to chart yet" body="Complete a few tasks and your progress will show up here, calculated from your own task history." />
      ) : (
        <>
          <section aria-label="Summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={`Done · ${days}d`} value={data.completed} />
            <Stat label="Pending" value={data.pending} hint={data.blocked ? `${data.blocked} blocked` : undefined} />
            <Stat label="Overdue" value={data.overdue} tone="bad" />
            <Stat
              label="On time"
              value={data.completed_with_deadline ? `${Math.round((data.completed_on_time / data.completed_with_deadline) * 100)}%` : "–"}
              hint={data.completed_with_deadline ? `${data.completed_on_time} of ${data.completed_with_deadline} with deadlines` : "No finished tasks had deadlines"}
            />
          </section>

          <section aria-label="Tasks completed per day" className="space-y-3">
            <h2 className="text-title">Completed per day</h2>
            <div className="rounded-2xl border bg-card p-4 shadow-card">
              <div className="h-56 w-full" role="img" aria-label={`Bar chart of tasks completed per day over the last ${days} days. A table with the same data follows.`}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.daily.map((d) => ({ ...d, label: dayLabel(d.date) }))} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--border)" />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} interval={days > 7 ? 4 : 0} stroke="var(--muted-foreground)" />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} stroke="var(--muted-foreground)" />
                    <Tooltip cursor={{ fill: "var(--muted)" }} contentStyle={{ borderRadius: 12, border: "1px solid var(--border)", background: "var(--popover)", fontSize: 13 }} formatter={(v) => [String(v), "Completed"]} />
                    <Bar dataKey="completed" fill="var(--sage)" radius={[6, 6, 0, 0]} maxBarSize={36} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <table className="sr-only">
                <caption>Tasks completed per day</caption>
                <thead><tr><th>Day</th><th>Completed</th><th>Minutes</th></tr></thead>
                <tbody>
                  {data.daily.map((d) => (
                    <tr key={d.date}><td>{dayLabel(d.date, true)}</td><td>{d.completed}</td><td>{d.completed_minutes}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {data.by_category.length > 0 && (
            <section aria-label="Progress by category" className="space-y-3">
              <h2 className="text-title">By category</h2>
              <ul className="space-y-3 rounded-2xl border bg-card p-4 shadow-card">
                {data.by_category.map((c) => {
                  const total = c.completed + c.pending;
                  return (
                    <li key={c.name} className="space-y-1.5">
                      <div className="flex items-baseline justify-between text-sm">
                        <span className="inline-flex items-center gap-2"><span className="size-2 rounded-full" style={{ backgroundColor: c.color }} aria-hidden />{c.name}</span>
                        <span className="tabular-nums text-muted-foreground">{c.completed}/{total} done</span>
                      </div>
                      <ProgressBar percent={total ? (c.completed / total) * 100 : 0} label={`${c.name}: ${c.completed} of ${total} done`} />
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          <section aria-label="Estimated versus actual time" className="space-y-3">
            <h2 className="text-title">Estimates vs reality</h2>
            {data.time_accuracy.tasks === 0 ? (
              <p className="rounded-2xl border border-dashed px-4 py-6 text-sm text-muted-foreground">
                Add an estimate <em>and</em> the actual time when you finish a task, and Daywise will show how well you predict your own effort.
              </p>
            ) : (
              <div className="space-y-4 rounded-2xl border bg-card p-5 shadow-card">
                <p className="text-sm">
                  Across <span className="font-medium">{data.time_accuracy.tasks}</span> finished {data.time_accuracy.tasks === 1 ? "task" : "tasks"} you estimated{" "}
                  <span className="font-medium">{formatMinutes(data.time_accuracy.estimated_minutes)}</span> and spent{" "}
                  <span className="font-medium">{formatMinutes(data.time_accuracy.actual_minutes)}</span>
                  {timeDelta !== 0 && <> ({formatMinutes(Math.abs(timeDelta))} {timeDelta > 0 ? "over" : "under"})</>}.
                </p>
                <ul className="space-y-1.5 text-sm">
                  {data.time_accuracy.biggest_misses.map((t) => (
                    <li key={t.id} className="flex items-baseline justify-between gap-3">
                      <Link href={`/tasks/${t.id}`} className="truncate hover:underline">{t.title}</Link>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">est. {formatMinutes(t.estimated_minutes ?? 0)} · actual {formatMinutes(t.actual_minutes ?? 0)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {data.projects.length > 0 && (
            <section aria-label="Project completion" className="space-y-3">
              <h2 className="text-title">Projects</h2>
              <ul className="space-y-3">
                {data.projects.map((p) => (
                  <li key={p.id} className="rounded-2xl border bg-card p-4 shadow-card">
                    <div className="flex items-baseline justify-between gap-3">
                      <Link href={`/projects/${p.id}`} className="font-medium hover:underline">{p.name}</Link>
                      <span className="text-sm tabular-nums text-muted-foreground">{Math.round(p.percent)}%{p.deadline ? ` · ${formatDeadline(p.deadline)}` : ""}</span>
                    </div>
                    <ProgressBar className="mt-2" percent={p.percent} label={`${p.name} progress`} />
                    <p className="mt-1.5 text-xs text-muted-foreground">{formatMinutes(p.remaining_minutes)} of work remaining</p>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
