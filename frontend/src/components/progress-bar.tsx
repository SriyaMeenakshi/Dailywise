import { cn } from "cn";
import { formatMinutes } from "@/lib/task-utils";
import type { Progress } from "@/lib/types";

export function ProgressBar({ percent, label, className }: { percent: number; label: string; className?: string }) {
  return (
    <div
      className={cn("h-1.5 overflow-hidden rounded-full bg-muted", className)}
      role="progressbar"
      aria-valuenow={Math.round(percent)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div className="h-full rounded-full bg-sage transition-[width] duration-500" style={{ width: `${percent}%` }} />
    </div>
  );
}

export function ProgressSummary({ progress }: { progress: Progress }) {
  return (
    <p className="text-xs tabular-nums text-muted-foreground">
      {progress.tasks_done}/{progress.tasks_total} tasks
      {progress.tasks_total > 0 && <> · {formatMinutes(progress.remaining_minutes)} left</>}
      {progress.unestimated_tasks > 0 && (
        <span title="Tasks without an estimate count as 30 minutes"> · {progress.unestimated_tasks} unestimated</span>
      )}
    </p>
  );
}
