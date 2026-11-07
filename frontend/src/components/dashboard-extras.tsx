"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CalendarDays } from "lucide-react";
import { ProgressBar } from "@/components/progress-bar";
import { useWorkspace } from "@/components/workspace-provider";
import { api } from "@/lib/api";
import { formatMinutes } from "@/lib/task-utils";
import type { Plan } from "@/lib/types";

const pad = (n: number) => String(n).padStart(2, "0");
const todayKey = () => {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

/** Today's planned and free time, from the saved plan. Hidden if it can't be loaded: it's optional. */
export function PlanSnapshot() {
  const [plan, setPlan] = useState<Plan | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.plan.get(todayKey()).then((p) => !cancelled && setPlan(p)).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  if (!plan) return null;
  const planned = plan.blocks.some((b) => b.kind !== "postponed");
  return (
    <Link href="/planner" className="flex items-center gap-4 rounded-2xl border bg-card p-4 shadow-card outline-none transition-colors hover:border-foreground/20 focus-visible:ring-3 focus-visible:ring-ring/50">
      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-clay-soft text-clay"><CalendarDays className="size-5" aria-hidden /></span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{planned ? "Today’s plan" : "Plan your day"}</span>
        <span className="block text-xs text-muted-foreground">
          {planned
            ? `${formatMinutes(plan.planned_minutes)} planned · ${formatMinutes(plan.free_minutes)} still free`
            : `${formatMinutes(plan.free_minutes)} available. Let Daywise fit your priorities in.`}
        </span>
      </span>
    </Link>
  );
}

/** The three active projects with the most work still to do. */
export function ProjectSnapshot() {
  const { projects } = useWorkspace();
  const active = projects
    .filter((p) => p.status === "active" && p.progress && p.progress.tasks_total > 0)
    .sort((a, b) => (b.progress?.remaining_minutes ?? 0) - (a.progress?.remaining_minutes ?? 0))
    .slice(0, 3);
  if (active.length === 0) return null;
  return (
    <section className="space-y-2.5" aria-label="Project progress">
      <h2 className="text-section">Projects</h2>
      <ul className="space-y-2">
        {active.map((p) => (
          <li key={p.id}>
            <Link href={`/projects/${p.id}`} className="block rounded-xl border bg-card px-3.5 py-3 shadow-card outline-none transition-colors hover:border-foreground/20 focus-visible:ring-3 focus-visible:ring-ring/50">
              <span className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate font-medium">{p.name}</span>
                <span className="tabular-nums text-muted-foreground">{Math.round(p.progress!.percent)}%</span>
              </span>
              <ProgressBar className="mt-2" percent={p.progress!.percent} label={`${p.name} progress`} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
