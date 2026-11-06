import { cn } from "cn";
import type { PriorityLevel } from "@/lib/types";

const STYLES: Record<PriorityLevel, string> = {
  critical: "bg-clay-soft text-clay",
  high: "bg-amber-soft text-amber",
  medium: "bg-sage-soft text-sage",
  low: "bg-muted text-muted-foreground",
};

export function PriorityBadge({ level, score, manual }: { level: PriorityLevel; score?: number; manual?: boolean }) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize", STYLES[level])}
      title={manual ? "Priority set manually" : "Calculated priority"}
    >
      {level}
      {score !== undefined && <span className="tabular-nums opacity-70">{Math.round(score)}</span>}
      {manual && <span aria-label="set manually">·&nbsp;manual</span>}
    </span>
  );
}
