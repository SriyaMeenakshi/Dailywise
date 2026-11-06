"use client";

import { AlertTriangle, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useWorkspace } from "@/components/workspace-provider";

export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2" role="status" aria-label="Loading tasks">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-[62px] w-full rounded-xl" />
      ))}
    </div>
  );
}

export function LoadError({ message }: { message: string }) {
  const { reload } = useWorkspace();
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-5">
      <div className="flex items-center gap-2 font-medium text-destructive">
        <AlertTriangle className="size-4" /> We couldn’t load your workspace
      </div>
      <p className="text-sm text-muted-foreground">{message}</p>
      <Button variant="outline" onClick={() => void reload()}>
        Try again
      </Button>
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed px-6 py-12 text-center">
      <div className="grid size-11 place-items-center rounded-full bg-clay-soft text-clay">
        <Inbox className="size-5" aria-hidden />
      </div>
      <h3 className="mt-4 text-lg">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
