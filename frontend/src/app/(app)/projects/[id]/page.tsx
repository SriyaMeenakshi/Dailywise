"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, CalendarClock, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { ProgressBar, ProgressSummary } from "@/components/progress-bar";
import { ProjectSheet, type ProjectPayload } from "@/components/project-form";
import { TaskRow } from "@/components/task-row";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ListSkeleton } from "@/components/workspace-states";
import { useWorkspace } from "@/components/workspace-provider";
import { api, ApiError } from "@/lib/api";
import { byUrgency, formatDeadline, formatMinutes } from "@/lib/task-utils";
import { PROJECT_STATUS_LABELS, type Phase, type Project } from "@/lib/types";

const short = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

function Timeline({ project, now }: { project: Project; now: number }) {
  const start = new Date(project.created_at).getTime();
  const end = project.deadline ? new Date(project.deadline).getTime() : null;
  if (!end || end <= start) {
    return <p className="text-sm text-muted-foreground">Set a project deadline to see how today sits on the timeline.</p>;
  }
  const todayPct = Math.min(100, Math.max(0, ((now - start) / (end - start)) * 100));
  const late = now > end && (project.progress?.percent ?? 0) < 100;
  return (
    <div className="space-y-2">
      <div className="relative h-2 rounded-full bg-muted" role="img" aria-label={`Today is ${Math.round(todayPct)}% of the way to the deadline`}>
        <div className={`absolute inset-y-0 left-0 rounded-full ${late ? "bg-destructive/60" : "bg-primary/25"}`} style={{ width: `${todayPct}%` }} />
        <div className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card bg-clay shadow-card" style={{ left: `${todayPct}%` }} />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Started {short(project.created_at)}</span>
        <span className={late ? "font-medium text-destructive" : undefined}>{late ? "Past deadline · " : "Due "}{short(project.deadline!)}</span>
      </div>
    </div>
  );
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { tasks, openEditor, refreshProjects } = useWorkspace();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [phaseName, setPhaseName] = useState("");
  const [now] = useState(() => Date.now());

  const load = useCallback(async () => {
    try {
      setProject(await api.projects.get(id));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 404 ? "This project doesn’t exist." : "Could not load this project.");
    }
  }, [id]);

  // Re-read whenever tasks change so progress always matches what's on screen.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sync with server-calculated progress
    void load();
  }, [load, tasks]);

  const mine = useMemo(() => tasks.filter((t) => t.project_id === id && t.status !== "archived").sort(byUrgency), [tasks, id]);

  async function save(payload: ProjectPayload) {
    try {
      await api.projects.update(id, payload);
      await Promise.all([load(), refreshProjects()]);
      toast.success("Project updated");
      return true;
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save");
      return false;
    }
  }

  async function remove() {
    if (!window.confirm("Delete this project? Its tasks are kept but will no longer belong to a project.")) return;
    try {
      await api.projects.remove(id);
      await refreshProjects();
      toast.success("Project deleted");
      router.replace("/projects");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not delete");
    }
  }

  async function addPhase(e: React.FormEvent) {
    e.preventDefault();
    const name = phaseName.trim();
    if (!name) return;
    try {
      await api.projects.addPhase(id, name);
      setPhaseName("");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add the phase");
    }
  }

  async function removePhase(phase: Phase) {
    if (!window.confirm(`Delete the phase “${phase.name}”? Its tasks stay in the project.`)) return;
    try {
      await api.phases.remove(phase.id);
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete the phase");
    }
  }

  if (error) {
    return (
      <div className="space-y-3">
        <p role="alert" className="text-destructive">{error}</p>
        <Link href="/projects" className="text-sm underline underline-offset-4">Back to projects</Link>
      </div>
    );
  }
  if (!project) return <ListSkeleton rows={3} />;

  const progress = project.progress;
  const unphased = mine.filter((t) => !t.phase_id);

  return (
    <div className="space-y-8">
      <div>
        <Link href="/projects" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Projects
        </Link>
        <div className="mt-3 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-display break-words">{project.name}</h1>
            <p className="mt-2 flex flex-wrap items-center gap-x-3 text-sm text-muted-foreground">
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{PROJECT_STATUS_LABELS[project.status]}</span>
              {project.deadline && (
                <span className="inline-flex items-center gap-1">
                  <CalendarClock className="size-4" aria-hidden /> {formatDeadline(project.deadline)}
                </span>
              )}
            </p>
          </div>
          <div className="flex shrink-0 gap-1">
            <Button variant="outline" size="icon" aria-label="Edit project" onClick={() => setEditing(true)}>
              <Pencil />
            </Button>
            <Button variant="outline" size="icon" aria-label="Delete project" onClick={remove}>
              <Trash2 />
            </Button>
          </div>
        </div>
        {project.objective && <p className="mt-4 max-w-2xl leading-relaxed text-muted-foreground">{project.objective}</p>}
      </div>

      {progress && (
        <section aria-label="Progress" className="space-y-5 rounded-2xl border bg-card p-5 shadow-card">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-section">Complete</p>
              <p className="font-display text-3xl tabular-nums">{Math.round(progress.percent)}%</p>
            </div>
            <div>
              <p className="text-section">Remaining</p>
              <p className="font-display text-3xl tabular-nums">{formatMinutes(progress.remaining_minutes)}</p>
            </div>
            <div>
              <p className="text-section">Tasks</p>
              <p className="font-display text-3xl tabular-nums">
                {progress.tasks_done}<span className="text-muted-foreground">/{progress.tasks_total}</span>
              </p>
            </div>
          </div>
          <ProgressBar percent={progress.percent} label="Project progress" />
          <p className="text-xs text-muted-foreground">
            Progress is weighted by estimated effort, so a 4-hour task counts for more than a 10-minute one.
            {progress.unestimated_tasks > 0 && ` ${progress.unestimated_tasks} task(s) have no estimate and count as 30 minutes.`}
          </p>
          <Timeline project={project} now={now} />
        </section>
      )}

      <section className="space-y-4" aria-label="Phases and tasks">
        <div className="flex items-center justify-between">
          <h2 className="text-title">Phases</h2>
          <div className="flex gap-2">
            <Link href={`/projects/breakdown?project=${id}`} className={buttonVariants({ variant: "outline" })}>
              <Sparkles className="text-clay" /> <span className="hidden sm:inline">Break down with AI</span>
              <span className="sm:hidden">AI</span>
            </Link>
            <Button variant="outline" onClick={() => openEditor(null, { project_id: id })}>
              <Plus /> Add task
            </Button>
          </div>
        </div>

        {project.phases.map((phase) => {
          const inPhase = mine.filter((t) => t.phase_id === phase.id);
          return (
            <div key={phase.id} className="space-y-2.5 rounded-2xl border bg-card/60 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-lg">{phase.name}</h3>
                  {phase.milestone && <p className="text-xs text-muted-foreground">Milestone: {phase.milestone}</p>}
                  <p className="text-xs text-muted-foreground">
                    {phase.earliest_deadline
                      ? phase.earliest_deadline === phase.latest_deadline
                        ? `Due ${short(phase.earliest_deadline)}`
                        : `${short(phase.earliest_deadline)} – ${short(phase.latest_deadline!)}`
                      : "No deadlines yet"}
                  </p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button variant="ghost" size="sm" onClick={() => openEditor(null, { project_id: id, phase_id: phase.id })}>
                    <Plus /> Task
                  </Button>
                  <Button variant="ghost" size="icon-sm" aria-label={`Delete phase ${phase.name}`} onClick={() => void removePhase(phase)}>
                    <Trash2 />
                  </Button>
                </div>
              </div>
              {phase.progress && (
                <div className="space-y-1.5">
                  <ProgressBar percent={phase.progress.percent} label={`${phase.name} progress`} />
                  <ProgressSummary progress={phase.progress} />
                </div>
              )}
              {inPhase.length > 0 ? (
                <ul className="space-y-2">{inPhase.map((t) => <TaskRow key={t.id} task={t} compact />)}</ul>
              ) : (
                <p className="rounded-xl border border-dashed px-4 py-4 text-sm text-muted-foreground">No tasks in this phase yet.</p>
              )}
            </div>
          );
        })}

        <form onSubmit={addPhase} className="flex gap-2">
          <Input value={phaseName} onChange={(e) => setPhaseName(e.target.value)} maxLength={200} placeholder="New phase, e.g. Research" aria-label="New phase name" />
          <Button type="submit" variant="secondary" disabled={!phaseName.trim()}>
            Add phase
          </Button>
        </form>

        {unphased.length > 0 && (
          <div className="space-y-2.5">
            <h3 className="text-section">Not in a phase · {unphased.length}</h3>
            <ul className="space-y-2">{unphased.map((t) => <TaskRow key={t.id} task={t} compact />)}</ul>
          </div>
        )}
        {project.phases.length === 0 && mine.length === 0 && (
          <p className="text-sm text-muted-foreground">Start by adding a phase (such as Research, Build, Polish) or a task.</p>
        )}
      </section>

      <ProjectSheet open={editing} project={project} onOpenChange={setEditing} onSubmit={save} />
    </div>
  );
}
