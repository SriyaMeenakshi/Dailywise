"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { CalendarClock, Plus, Sparkles } from "lucide-react";
import { ProgressBar, ProgressSummary } from "@/components/progress-bar";
import { ProjectSheet, type ProjectPayload } from "@/components/project-form";
import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState, ListSkeleton, LoadError } from "@/components/workspace-states";
import { useWorkspace } from "@/components/workspace-provider";
import { api, ApiError } from "@/lib/api";
import { formatDeadline } from "@/lib/task-utils";
import { PROJECT_STATUS_LABELS } from "@/lib/types";

export default function ProjectsPage() {
  const router = useRouter();
  const { projects, loading, loadError, refreshProjects } = useWorkspace();
  const [creating, setCreating] = useState(false);

  async function create(payload: ProjectPayload) {
    try {
      const project = await api.projects.create(payload);
      await refreshProjects();
      toast.success("Project created");
      router.push(`/projects/${project.id}`);
      return true;
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not create the project");
      return false;
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <p className="text-section">Big goals, broken down</p>
          <h1 className="text-display mt-1">Projects</h1>
        </div>
        <div className="flex gap-2">
          <Link href="/projects/breakdown" className={buttonVariants({ variant: "outline" })}>
            <Sparkles className="text-clay" /> <span className="hidden sm:inline">Break down with AI</span>
            <span className="sm:hidden">AI</span>
          </Link>
          <Button onClick={() => setCreating(true)}>
            <Plus /> New project
          </Button>
        </div>
      </header>

      {loadError ? (
        <LoadError message={loadError} />
      ) : loading ? (
        <ListSkeleton rows={3} />
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          body="A project groups related tasks into phases and tracks progress by effort, not by task count."
          action={<Button onClick={() => setCreating(true)}>Create your first project</Button>}
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {projects.map((p) => (
            <li key={p.id}>
              <Link
                href={`/projects/${p.id}`}
                className="block h-full rounded-2xl border bg-card p-5 shadow-card outline-none transition-colors hover:border-foreground/20 focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-xl leading-snug">{p.name}</h2>
                  {p.status !== "active" && (
                    <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {PROJECT_STATUS_LABELS[p.status]}
                    </span>
                  )}
                </div>
                {p.objective && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{p.objective}</p>}
                <div className="mt-4 space-y-2">
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="tabular-nums font-medium">{Math.round(p.progress?.percent ?? 0)}%</span>
                    {p.deadline && (
                      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                        <CalendarClock className="size-3.5" aria-hidden /> {formatDeadline(p.deadline)}
                      </span>
                    )}
                  </div>
                  <ProgressBar percent={p.progress?.percent ?? 0} label={`${p.name} progress`} />
                  {p.progress && <ProgressSummary progress={p.progress} />}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <ProjectSheet open={creating} project={null} onOpenChange={setCreating} onSubmit={create} />
    </div>
  );
}
