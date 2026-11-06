"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { cn } from "cn";
import { QuickAdd } from "@/components/quick-add";
import { TaskRow } from "@/components/task-row";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { EmptyState, ListSkeleton, LoadError } from "@/components/workspace-states";
import { useWorkspace } from "@/components/workspace-provider";
import { byUrgency, isActive } from "@/lib/task-utils";
import { STATUS_LABELS, TASK_STATUSES, type Task, type TaskStatus } from "@/lib/types";

type StatusFilter = "active" | "all" | TaskStatus;
type Sort = "priority" | "deadline" | "importance" | "newest" | "title";

const FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "inbox", label: "Inbox" },
  { value: "in_progress", label: "In progress" },
  { value: "blocked", label: "Blocked" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
  { value: "all", label: "All" },
];

const SORTERS: Record<Sort, (a: Task, b: Task) => number> = {
  priority: (a, b) => b.priority_score - a.priority_score || byUrgency(a, b),
  deadline: byUrgency,
  importance: (a, b) => b.importance - a.importance || byUrgency(a, b),
  newest: (a, b) => b.created_at.localeCompare(a.created_at),
  title: (a, b) => a.title.localeCompare(b.title),
};

function TasksView() {
  const params = useSearchParams();
  const initial = params.get("status");
  const { tasks, categories, loading, loadError, openEditor } = useWorkspace();
  const [status, setStatus] = useState<StatusFilter>(
    initial && (TASK_STATUSES as readonly string[]).includes(initial) ? (initial as TaskStatus) : "active",
  );
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState<Sort>("priority");
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tasks
      .filter((t) => {
        if (status === "active" ? !isActive(t) : status !== "all" && t.status !== status) return false;
        if (category && t.category_id !== category) return false;
        return !q || t.title.toLowerCase().includes(q) || (t.description ?? "").toLowerCase().includes(q);
      })
      .sort(SORTERS[sort]);
  }, [tasks, status, category, sort, query]);

  const filtering = Boolean(query || category || status !== "active");

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <h1 className="text-display">Tasks</h1>
        <p className="pb-1.5 text-sm tabular-nums text-muted-foreground">{visible.length} shown</p>
      </header>

      <QuickAdd />

      <div className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tasks"
              aria-label="Search tasks"
              className="pl-9"
            />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <NativeSelect aria-label="Filter by category" value={category} onChange={(e) => setCategory(e.target.value)} className="sm:w-44">
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect aria-label="Sort tasks" value={sort} onChange={(e) => setSort(e.target.value as Sort)} className="sm:w-40">
              <option value="priority">Sort: Priority</option>
              <option value="deadline">Sort: Deadline</option>
              <option value="importance">Sort: Importance</option>
              <option value="newest">Sort: Newest</option>
              <option value="title">Sort: Title</option>
            </NativeSelect>
          </div>
        </div>
        <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0" role="group" aria-label="Filter by status">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              aria-pressed={status === f.value}
              onClick={() => setStatus(f.value)}
              className={cn(
                "shrink-0 rounded-full border px-3 py-1 text-sm transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                status === f.value ? "border-primary bg-primary text-primary-foreground" : "bg-card text-muted-foreground hover:text-foreground",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loadError ? (
        <LoadError message={loadError} />
      ) : loading ? (
        <ListSkeleton rows={5} />
      ) : visible.length === 0 ? (
        filtering ? (
          <EmptyState
            title="No tasks match"
            body={`Nothing found${status !== "active" ? ` in “${status === "all" ? "All" : STATUS_LABELS[status as TaskStatus]}”` : ""}. Try clearing the search or filters.`}
            action={
              <Button
                variant="outline"
                onClick={() => {
                  setQuery("");
                  setCategory("");
                  setStatus("active");
                }}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            title="No tasks yet"
            body="Type a task above and press Enter to capture it. Add the details later."
            action={<Button onClick={() => openEditor(null)}>Add with details</Button>}
          />
        )
      ) : (
        <ul className="space-y-2">
          {visible.map((t) => (
            <TaskRow key={t.id} task={t} />
          ))}
        </ul>
      )}
    </div>
  );
}

export default function TasksPage() {
  return (
    <Suspense fallback={<ListSkeleton rows={5} />}>
      <TasksView />
    </Suspense>
  );
}
