"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Sparkles, X } from "lucide-react";
import { AIUsage, useAIStatus } from "@/components/ai-usage";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useWorkspace } from "@/components/workspace-provider";
import { api, ApiError } from "@/lib/api";
import { formatMinutes } from "@/lib/task-utils";
import type { Breakdown, PlanTask } from "@/lib/types";

type DraftTask = PlanTask & { include: boolean; estimate: string };
interface DraftPhase {
  name: string;
  milestone: string | null;
  tasks: DraftTask[];
}
interface Draft {
  project_name: string;
  objective: string;
  phases: DraftPhase[];
}

const toDraft = (b: Breakdown): Draft => ({
  project_name: b.project_name,
  objective: b.objective ?? "",
  phases: b.phases.map((p) => ({
    name: p.name,
    milestone: p.milestone,
    tasks: p.tasks.map((t) => ({ ...t, include: true, estimate: t.estimated_minutes ? String(t.estimated_minutes) : "" })),
  })),
});

const validEstimate = (t: DraftTask) => t.estimate.trim() === "" || (/^\d+$/.test(t.estimate.trim()) && Number(t.estimate) > 0);

function BreakdownView() {
  const router = useRouter();
  const targetId = useSearchParams().get("project");
  const { projects, refreshProjects, refreshTasks } = useWorkspace();
  const target = projects.find((p) => p.id === targetId) ?? null;
  const { status, refresh } = useAIStatus();

  const [goal, setGoal] = useState("");
  const [context, setContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [notes, setNotes] = useState<{ cached: boolean; truncated: boolean } | null>(null);
  const [applying, setApplying] = useState(false);

  async function generate(force = false) {
    if (goal.trim().length < 3 || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.ai.decompose(goal, context, force);
      setDraft(toDraft(res));
      setNotes({ cached: res.cached, truncated: res.truncated });
    } catch (e) {
      setDraft(null);
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  const patchTask = (pi: number, ti: number, patch: Partial<DraftTask>) =>
    setDraft((d) => d && { ...d, phases: d.phases.map((p, i) => (i !== pi ? p : { ...p, tasks: p.tasks.map((t, j) => (j === ti ? { ...t, ...patch } : t)) })) });

  const summary = useMemo(() => {
    if (!draft) return { tasks: 0, minutes: 0, phases: 0 };
    const included = draft.phases.map((p) => p.tasks.filter((t) => t.include));
    return {
      tasks: included.flat().length,
      phases: included.filter((t) => t.length > 0).length,
      minutes: included.flat().reduce((sum, t) => sum + (Number(t.estimate) || 0), 0),
    };
  }, [draft]);
  const titleOf = useMemo(() => new Map(draft?.phases.flatMap((p) => p.tasks.map((t) => [t.ref, t.title])) ?? []), [draft]);

  async function apply() {
    if (!draft || summary.tasks === 0) return;
    const kept = new Set(draft.phases.flatMap((p) => p.tasks.filter((t) => t.include).map((t) => t.ref)));
    const body = {
      project_name: draft.project_name.trim() || "New project",
      objective: draft.objective.trim() || null,
      project_id: target?.id ?? null,
      phases: draft.phases
        .map((p) => ({
          name: p.name.trim() || "Phase",
          milestone: p.milestone,
          tasks: p.tasks
            .filter((t) => t.include)
            .map((t) => ({
              ref: t.ref,
              title: t.title.trim(),
              description: t.description,
              estimated_minutes: t.estimate.trim() ? Number(t.estimate) : null,
              subtasks: t.subtasks,
              depends_on: t.depends_on.filter((d) => kept.has(d)), // a removed task can't be depended on
            })),
        }))
        .filter((p) => p.tasks.length > 0),
    };
    setApplying(true);
    try {
      const res = await api.ai.applyBreakdown(body);
      await Promise.all([refreshProjects(), refreshTasks()]);
      toast.success(`Created ${res.tasks_created} tasks in ${res.phases_created} ${res.phases_created === 1 ? "phase" : "phases"}`);
      router.push(`/projects/${res.project_id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not create the plan");
      setApplying(false);
    }
  }

  const aiOff = status !== null && !status.configured;
  return (
    <div className="space-y-6">
      <div>
        <Link href={target ? `/projects/${target.id}` : "/projects"} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> {target ? target.name : "Projects"}
        </Link>
        <h1 className="text-display mt-3">Break down a goal</h1>
        <p className="mt-2 max-w-xl text-muted-foreground">
          Describe a big goal. You’ll get a draft with phases, tasks, subtasks and dependencies to edit. Nothing is created until you approve it.
          {target && <> New phases will be added to <span className="font-medium text-foreground">{target.name}</span>.</>}
        </p>
      </div>

      <AIUsage status={status} />

      <section className="space-y-3">
        <div className="space-y-1.5">
          <label htmlFor="goal" className="text-sm font-medium">The goal</label>
          <Input id="goal" value={goal} maxLength={500} onChange={(e) => setGoal(e.target.value)} placeholder="e.g. Build a full-stack AI application" disabled={aiOff} />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="context" className="text-sm font-medium">Anything that should shape the plan <span className="font-normal text-muted-foreground">(optional)</span></label>
          <Textarea id="context" rows={3} value={context} maxLength={2000} onChange={(e) => setContext(e.target.value)} placeholder="Skills, tools, time available, constraints…" disabled={aiOff} />
        </div>
        <Button onClick={() => void generate()} disabled={busy || goal.trim().length < 3 || aiOff}>
          <Sparkles /> {busy ? "Drafting a plan…" : "Draft a plan"}
        </Button>
      </section>

      {error && <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</p>}

      {draft && (
        <section className="space-y-5" aria-label="Review the draft plan">
          <h2 className="text-title">Review</h2>
          {notes?.cached && <p role="status" className="text-xs text-muted-foreground">Reused an earlier answer for this exact goal: no AI credit used.</p>}
          {notes?.truncated && (
            <p role="status" className="rounded-xl border border-amber/40 bg-amber-soft px-4 py-3 text-sm">The AI proposed more than we create at once, so the draft was trimmed. You can add more later.</p>
          )}

          {!target && (
            <div className="space-y-3 rounded-2xl border bg-card p-4 shadow-card">
              <div className="space-y-1.5">
                <label htmlFor="pname" className="text-xs text-muted-foreground">Project name</label>
                <Input id="pname" value={draft.project_name} maxLength={200} onChange={(e) => setDraft({ ...draft, project_name: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="pobj" className="text-xs text-muted-foreground">Objective</label>
                <Textarea id="pobj" rows={2} value={draft.objective} onChange={(e) => setDraft({ ...draft, objective: e.target.value })} />
              </div>
            </div>
          )}

          {draft.phases.map((phase, pi) => (
            <div key={pi} className="space-y-3 rounded-2xl border bg-card/60 p-4">
              <div className="space-y-1">
                <Input aria-label={`Phase ${pi + 1} name`} value={phase.name} maxLength={200} className="font-display text-lg" onChange={(e) => setDraft({ ...draft, phases: draft.phases.map((p, i) => (i === pi ? { ...p, name: e.target.value } : p)) })} />
                {phase.milestone && <p className="px-1 text-xs text-muted-foreground">Milestone: {phase.milestone}</p>}
              </div>
              <ul className="space-y-2">
                {phase.tasks.map((t, ti) => (
                  <li key={t.ref} className={`rounded-xl border bg-card p-3 transition-opacity ${t.include ? "" : "opacity-50"}`}>
                    <div className="flex items-start gap-3">
                      <Checkbox aria-label={`Include “${t.title}”`} checked={t.include} onCheckedChange={(v) => patchTask(pi, ti, { include: Boolean(v) })} className="mt-2.5" />
                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex gap-2">
                          <Input aria-label="Task title" value={t.title} maxLength={300} onChange={(e) => patchTask(pi, ti, { title: e.target.value })} aria-invalid={!t.title.trim()} />
                          <Input aria-label={`Estimate in minutes for ${t.title}`} inputMode="numeric" className="w-24" placeholder="min" value={t.estimate} onChange={(e) => patchTask(pi, ti, { estimate: e.target.value })} aria-invalid={!validEstimate(t)} />
                        </div>
                        {t.depends_on.length > 0 && (
                          <p className="text-xs text-muted-foreground">After: {t.depends_on.map((d) => titleOf.get(d) ?? d).join(", ")}</p>
                        )}
                        {t.subtasks.length > 0 && (
                          <ul className="space-y-1 pl-1 text-sm text-muted-foreground">
                            {t.subtasks.map((s, si) => (
                              <li key={si} className="flex items-center gap-2">
                                <span aria-hidden>·</span>
                                <span className="flex-1">{s.title}</span>
                                <button type="button" aria-label={`Remove subtask ${s.title}`} className="rounded p-0.5 hover:text-foreground" onClick={() => patchTask(pi, ti, { subtasks: t.subtasks.filter((_, k) => k !== si) })}>
                                  <X className="size-3.5" />
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          <div className="sticky bottom-20 flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-card/95 p-3 shadow-raised backdrop-blur md:bottom-4">
            <p className="text-sm tabular-nums text-muted-foreground">
              {summary.tasks} tasks · {summary.phases} phases{summary.minutes > 0 && ` · ${formatMinutes(summary.minutes)}`}
            </p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => void generate(true)} disabled={busy} title="Ask the AI again (uses one request)">Redraft</Button>
              <Button variant="outline" onClick={() => setDraft(null)}>Discard</Button>
              <Button onClick={() => void apply()} disabled={applying || summary.tasks === 0 || draft.phases.some((p) => p.tasks.some((t) => t.include && (!t.title.trim() || !validEstimate(t))))}>
                {applying ? "Creating…" : `Create ${summary.tasks} tasks`}
              </Button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

export default function BreakdownPage() {
  return (
    <Suspense fallback={null}>
      <BreakdownView />
    </Suspense>
  );
}
