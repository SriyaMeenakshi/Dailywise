"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, CalendarClock, Clock, FolderKanban, Pencil, Plus, Trash2, X } from "lucide-react";
import { PriorityBadge } from "@/components/priority-badge";
import { ProgressBar } from "@/components/progress-bar";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { ListSkeleton } from "@/components/workspace-states";
import { useWorkspace } from "@/components/workspace-provider";
import { api, ApiError } from "@/lib/api";
import { formatDeadline, formatMinutes, isActive } from "@/lib/task-utils";
import { ENERGY_LABELS, STATUS_LABELS, type Subtask, type Task, type TaskLog } from "@/lib/types";

const fail = (e: unknown, fallback: string) => toast.error(e instanceof ApiError ? e.message : fallback);

function Card({ title, children, aside }: { title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-2xl border bg-card p-5 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-section">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function describe(log: TaskLog): string {
  const d = (log.detail ?? {}) as Record<string, unknown>;
  switch (log.action) {
    case "created":
      return "Task created";
    case "subtask_added":
      return `Added subtask “${String(d.title)}”`;
    case "subtask_completed":
      return `Finished subtask “${String(d.title)}”`;
    case "dependency_added":
      return `Now waits on “${String(d.depends_on)}”`;
    case "dependency_removed":
      return `No longer waits on “${String(d.depends_on)}”`;
    default: {
      const show = (v: unknown) => (v === null || v === undefined || v === "" ? "none" : String(v));
      const parts = Object.entries(d).map(([field, change]) => {
        const name = field.replace(/_id$/, "").replaceAll("_", " ");
        if (!change || typeof change !== "object") return name;
        const { from, to } = change as { from: unknown; to: unknown };
        if (field.endsWith("_id")) return `${name} changed`; // ids mean nothing to a reader
        if (field === "deadline") {
          const when = (v: unknown) => (v ? new Date(String(v)).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "none");
          return `deadline: ${when(from)} → ${when(to)}`;
        }
        return `${name}: ${show(from)} → ${show(to)}`;
      });
      return parts.join(" · ") || "Updated";
    }
  }
}

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { tasks, projects, categories, toggleComplete, updateTask, deleteTask, openEditor, refreshTasks } = useWorkspace();
  const [task, setTask] = useState<Task | null>(null);
  const [subtasks, setSubtasks] = useState<Subtask[]>([]);
  const [history, setHistory] = useState<TaskLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newSubtask, setNewSubtask] = useState("");
  const [depChoice, setDepChoice] = useState("");
  const [override, setOverride] = useState("");

  const load = useCallback(async () => {
    try {
      const [t, s, h] = await Promise.all([api.tasks.get(id), api.tasks.subtasks.list(id), api.tasks.history(id)]);
      setTask(t);
      setSubtasks(s);
      setHistory(h);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 404 ? "This task doesn’t exist." : "Could not load this task.");
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reload after any workspace change
    void load();
  }, [load, tasks]);

  const byId = useMemo(() => new Map(tasks.map((t) => [t.id, t])), [tasks]);
  const blocks = useMemo(() => tasks.filter((t) => t.dependency_ids.includes(id) && isActive(t)), [tasks, id]);
  // Offer only tasks that wouldn't create a loop: not ones that already (transitively) wait on this task.
  const candidates = useMemo(() => {
    const waitingOnThis = new Set<string>([id]);
    let grew = true;
    while (grew) {
      grew = false;
      for (const t of tasks) {
        if (!waitingOnThis.has(t.id) && t.dependency_ids.some((d) => waitingOnThis.has(d))) {
          waitingOnThis.add(t.id);
          grew = true;
        }
      }
    }
    return tasks.filter((t) => !waitingOnThis.has(t.id) && isActive(t) && !task?.dependency_ids.includes(t.id));
  }, [tasks, id, task]);

  if (error) {
    return (
      <div className="space-y-3">
        <p role="alert" className="text-destructive">{error}</p>
        <Link href="/tasks" className="text-sm underline underline-offset-4">Back to tasks</Link>
      </div>
    );
  }
  if (!task) return <ListSkeleton rows={3} />;

  const done = task.status === "completed";
  const project = projects.find((p) => p.id === task.project_id);
  const category = categories.find((c) => c.id === task.category_id);
  const subDone = subtasks.filter((s) => s.done).length;

  async function addSubtask(e: React.FormEvent) {
    e.preventDefault();
    const title = newSubtask.trim();
    if (!title) return;
    try {
      await api.tasks.subtasks.create(id, { title });
      setNewSubtask("");
      await load();
    } catch (err) {
      fail(err, "Could not add the subtask");
    }
  }

  async function toggleSubtask(s: Subtask) {
    setSubtasks((prev) => prev.map((x) => (x.id === s.id ? { ...x, done: !s.done } : x)));
    try {
      await api.subtasks.update(s.id, { done: !s.done });
      await load();
    } catch (err) {
      fail(err, "Could not update the subtask");
      await load();
    }
  }

  async function removeSubtask(s: Subtask) {
    try {
      await api.subtasks.remove(s.id);
      await load();
    } catch (err) {
      fail(err, "Could not delete the subtask");
    }
  }

  async function addDependency() {
    if (!depChoice) return;
    try {
      await api.tasks.addDependency(id, depChoice);
      setDepChoice("");
      await refreshTasks();
    } catch (err) {
      fail(err, "Could not add the dependency");
    }
  }

  async function removeDependency(depId: string) {
    try {
      await api.tasks.removeDependency(id, depId);
      await refreshTasks();
    } catch (err) {
      fail(err, "Could not remove the dependency");
    }
  }

  async function applyOverride(value: number | null) {
    if (value !== null && (!Number.isInteger(value) || value < 0 || value > 100)) {
      toast.error("Enter a whole number from 0 to 100");
      return;
    }
    if (await updateTask(id, { priority_override: value })) {
      setOverride("");
      await refreshTasks();
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href="/tasks" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Tasks
        </Link>
        <div className="mt-3 flex items-start gap-3">
          <Checkbox
            aria-label={done ? "Mark as not done" : "Mark as done"}
            checked={done}
            onCheckedChange={() => void toggleComplete(task)}
            className="mt-2 size-5 rounded-full"
          />
          <h1 className={`text-display min-w-0 flex-1 break-words ${done ? "text-muted-foreground line-through" : ""}`}>{task.title}</h1>
          <div className="flex shrink-0 gap-1">
            <Button variant="outline" size="icon" aria-label="Edit task" onClick={() => openEditor(task)}>
              <Pencil />
            </Button>
            <Button
              variant="outline"
              size="icon"
              aria-label="Delete task"
              onClick={async () => {
                if (!window.confirm("Delete this task? This can’t be undone.")) return;
                await deleteTask(id);
                router.replace("/tasks");
              }}
            >
              <Trash2 />
            </Button>
          </div>
        </div>
        <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground">
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{STATUS_LABELS[task.status]}</span>
          {category && (
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ backgroundColor: category.color }} aria-hidden /> {category.name}
            </span>
          )}
          {project && (
            <Link href={`/projects/${project.id}`} className="inline-flex items-center gap-1 hover:text-foreground">
              <FolderKanban className="size-4" aria-hidden /> {project.name}
            </Link>
          )}
          {task.deadline && (
            <span className="inline-flex items-center gap-1">
              <CalendarClock className="size-4" aria-hidden /> {formatDeadline(task.deadline)}
            </span>
          )}
          {task.estimated_minutes && (
            <span className="inline-flex items-center gap-1">
              <Clock className="size-4" aria-hidden /> {formatMinutes(task.estimated_minutes)}
            </span>
          )}
          <span>{ENERGY_LABELS[task.energy]} energy</span>
        </p>
        {task.description && <p className="mt-4 max-w-2xl whitespace-pre-wrap leading-relaxed">{task.description}</p>}
        {task.expected_outcome && (
          <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Done looks like: </span>
            {task.expected_outcome}
          </p>
        )}
        {task.notes && <p className="mt-3 max-w-2xl whitespace-pre-wrap text-sm text-muted-foreground">{task.notes}</p>}
      </div>

      <Card title="Priority" aside={<PriorityBadge level={task.priority_level} score={task.priority_score} manual={task.priority_override !== null} />}>
        {task.priority_explanation && <p className="text-sm leading-relaxed">{task.priority_explanation}</p>}
        {task.priority_factors && !done && task.status !== "archived" && (
          <ul className="space-y-2.5 pt-1" aria-label="How the score is made up">
            {task.priority_factors.map((f) => (
              <li key={f.key} className="grid grid-cols-[8.5rem_1fr_auto] items-center gap-3 text-sm">
                <span>{f.label}</span>
                <ProgressBar percent={f.value} label={`${f.label} ${f.value} out of 100`} />
                <span className="w-24 text-right text-xs tabular-nums text-muted-foreground">
                  {f.value} × {Math.round(f.weight * 100)}% = {f.contribution}
                </span>
              </li>
            ))}
          </ul>
        )}
        {!done && task.status !== "archived" && (
          <form
            className="flex flex-wrap items-center gap-2 border-t pt-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (override.trim() !== "") void applyOverride(Number(override));
            }}
          >
            <label htmlFor="override" className="text-sm font-medium">
              Set manually
            </label>
            <Input
              id="override"
              inputMode="numeric"
              className="w-20"
              placeholder="0–100"
              value={override}
              onChange={(e) => setOverride(e.target.value)}
            />
            <Button type="submit" variant="secondary" disabled={override.trim() === ""}>
              Apply
            </Button>
            {task.priority_override !== null && (
              <Button type="button" variant="ghost" onClick={() => void applyOverride(null)}>
                Use calculated ({Math.round(task.priority_computed)})
              </Button>
            )}
          </form>
        )}
      </Card>

      <Card
        title="Subtasks"
        aside={subtasks.length > 0 && <span className="text-xs tabular-nums text-muted-foreground">{subDone}/{subtasks.length} done</span>}
      >
        {subtasks.length > 0 && <ProgressBar percent={(subDone / subtasks.length) * 100} label="Subtask progress" />}
        <ul className="space-y-1.5">
          {subtasks.map((s) => (
            <li key={s.id} className="group flex items-center gap-3 rounded-lg px-1 py-1">
              <Checkbox aria-label={`Mark “${s.title}” ${s.done ? "not done" : "done"}`} checked={s.done} onCheckedChange={() => void toggleSubtask(s)} />
              <span className={`flex-1 text-sm ${s.done ? "text-muted-foreground line-through" : ""}`}>{s.title}</span>
              <Button variant="ghost" size="icon-xs" aria-label={`Delete subtask ${s.title}`} onClick={() => void removeSubtask(s)} className="opacity-60 group-hover:opacity-100">
                <X />
              </Button>
            </li>
          ))}
        </ul>
        <form onSubmit={addSubtask} className="flex gap-2">
          <Input value={newSubtask} onChange={(e) => setNewSubtask(e.target.value)} maxLength={300} placeholder="Add a subtask" aria-label="New subtask" />
          <Button type="submit" variant="secondary" disabled={!newSubtask.trim()}>
            <Plus /> Add
          </Button>
        </form>
      </Card>

      <Card title="Dependencies">
        <div className="space-y-4 text-sm">
          <div className="space-y-2">
            <p className="text-muted-foreground">This task waits on</p>
            {task.dependency_ids.length === 0 ? (
              <p className="text-muted-foreground/80">Nothing. It can start any time.</p>
            ) : (
              <ul className="space-y-1.5">
                {task.dependency_ids.map((depId) => {
                  const dep = byId.get(depId);
                  return (
                    <li key={depId} className="flex items-center gap-2">
                      <Link href={`/tasks/${depId}`} className={`flex-1 truncate hover:underline ${dep?.status === "completed" ? "text-muted-foreground line-through" : ""}`}>
                        {dep?.title ?? "Unknown task"}
                      </Link>
                      <Button variant="ghost" size="icon-xs" aria-label={`Remove dependency on ${dep?.title ?? "task"}`} onClick={() => void removeDependency(depId)}>
                        <X />
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
            {candidates.length > 0 && (
              <div className="flex gap-2 pt-1">
                <NativeSelect aria-label="Choose a task this one waits on" value={depChoice} onChange={(e) => setDepChoice(e.target.value)}>
                  <option value="">Choose a task…</option>
                  {candidates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </NativeSelect>
                <Button variant="secondary" onClick={() => void addDependency()} disabled={!depChoice}>
                  Add
                </Button>
              </div>
            )}
          </div>
          {blocks.length > 0 && (
            <div className="space-y-1.5 border-t pt-3">
              <p className="text-muted-foreground">Finishing this unblocks</p>
              <ul className="space-y-1">
                {blocks.map((t) => (
                  <li key={t.id}>
                    <Link href={`/tasks/${t.id}`} className="hover:underline">{t.title}</Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </Card>

      <Card title="History">
        <ol className="space-y-3">
          {history.map((h) => (
            <li key={h.id} className="grid grid-cols-[7.5rem_1fr] gap-3 text-sm">
              <time dateTime={h.created_at} className="text-xs text-muted-foreground tabular-nums">
                {new Date(h.created_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}
              </time>
              <span>{describe(h)}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
