"use client";

import { useCallback, useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { AIStatus } from "@/lib/types";

export function useAIStatus() {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.ai.status());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial load of server-side usage
    void refresh();
  }, [refresh]);

  return { status, failed, refresh };
}

/** Shows exactly how much of today's AI allowance is used, so nothing is spent by surprise. */
export function AIUsage({ status }: { status: AIStatus | null }) {
  if (!status) return null;
  if (!status.configured) {
    return (
      <p role="status" className="rounded-xl border border-amber/40 bg-amber-soft px-4 py-3 text-sm">
        AI isn’t set up on this server, so these suggestions are unavailable. Tasks, priorities, projects and the daily
        planner all work without it.
      </p>
    );
  }
  const pct = Math.min(100, (status.requests_today / Math.max(status.request_limit, 1)) * 100);
  return (
    <div className="space-y-2 rounded-xl border bg-card px-4 py-3 text-sm shadow-card" aria-label="AI usage today">
      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 font-medium">
          <Sparkles className="size-4 text-clay" aria-hidden /> AI today
        </span>
        <span className="tabular-nums text-muted-foreground">
          {status.requests_today} of {status.request_limit} requests
        </span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label="AI requests used today">
        <div className={`h-full rounded-full ${pct >= 90 ? "bg-destructive/70" : "bg-clay"}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-muted-foreground">
        {status.tokens_today.toLocaleString()} / {status.token_limit.toLocaleString()} tokens
        {status.cost_tracking ? ` · about $${status.cost_today_usd.toFixed(4)}` : " · cost tracking off"}
        {status.cached_today > 0 && ` · ${status.cached_today} answered from cache, free`}
        {status.model && ` · ${status.model}`}
      </p>
    </div>
  );
}
