"use client";

import Link from "next/link";
import { Archive, CalendarClock, Clock, FolderKanban, Link2, MoreHorizontal, Pencil, RotateCcw, Trash2 } from "lucide-react";
import { cn } from "cn";
import { PriorityBadge } from "@/components/priority-badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useWorkspace } from "@/components/workspace-provider";
import { formatDeadline, formatMinutes, isDone, isOverdue } from "@/lib/task-utils";
import { STATUS_LABELS, type Task } from "@/lib/types";

export function TaskRow({ task, compact = false }: { task: Task; compact?: boolean }) {
  const { categories, projects, toggleComplete, openEditor, updateTask, deleteTask } = useWorkspace();
  const category = categories.find((c) => c.id === task.category_id);
  const project = projects.find((p) => p.id === task.project_id);
  const done = isDone(task);
  const overdue = isOverdue(task);
  const archived = task.status === "archived";

  return (
    <li
      className={cn(
        "group flex items-start gap-3 rounded-xl border bg-card px-3.5 py-3 shadow-card transition-colors hover:border-foreground/20",
        done && "bg-card/60",
      )}
    >
      <Checkbox
        aria-label={done ? `Mark "${task.title}" as not done` : `Mark "${task.title}" as done`}
        checked={done}
        disabled={archived}
        onCheckedChange={() => void toggleComplete(task)}
        className="mt-0.5 size-[18px] rounded-full"
      />
      <Link
        href={`/tasks/${task.id}`}
        className="min-w-0 flex-1 rounded-md text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <span className={cn("block truncate text-[15px] font-medium", done && "text-muted-foreground line-through")}>
          {task.title}
        </span>
        <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {category && (
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ backgroundColor: category.color }} aria-hidden />
              {category.name}
            </span>
          )}
          {task.deadline && (
            <span className={cn("inline-flex items-center gap-1", overdue && "font-medium text-destructive")}>
              <CalendarClock className="size-3.5" aria-hidden />
              {overdue ? "Overdue · " : ""}
              {formatDeadline(task.deadline)}
            </span>
          )}
          {task.estimated_minutes && (
            <span className="inline-flex items-center gap-1">
              <Clock className="size-3.5" aria-hidden />
              {formatMinutes(task.estimated_minutes)}
            </span>
          )}
          {!compact && task.status !== "not_started" && !done && (
            <span className="rounded-full bg-muted px-2 py-0.5">{STATUS_LABELS[task.status]}</span>
          )}
          {project && !compact && (
            <span className="inline-flex items-center gap-1">
              <FolderKanban className="size-3.5" aria-hidden />
              {project.name}
            </span>
          )}
          {task.waiting_on_count > 0 && !done && (
            <span className="inline-flex items-center gap-1 text-amber">
              <Link2 className="size-3.5" aria-hidden />
              Waiting on {task.waiting_on_count}
            </span>
          )}
          {!done && !archived && (task.priority_level === "critical" || task.priority_level === "high") && (
            <PriorityBadge level={task.priority_level} score={task.priority_score} manual={task.priority_override !== null} />
          )}
        </span>
      </Link>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button variant="ghost" size="icon-sm" aria-label={`Actions for ${task.title}`} />}
          className="opacity-60 group-hover:opacity-100 focus-visible:opacity-100"
        >
          <MoreHorizontal />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => openEditor(task)}>
            <Pencil /> Edit
          </DropdownMenuItem>
          {archived ? (
            <DropdownMenuItem onClick={() => void updateTask(task.id, { status: "not_started" })}>
              <RotateCcw /> Restore
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem onClick={() => void updateTask(task.id, { status: "archived" })}>
              <Archive /> Archive
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onClick={() => void deleteTask(task.id)}>
            <Trash2 /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  );
}
