"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ChevronRight, SlidersHorizontal } from "lucide-react";
import { PriorityBadge } from "@/components/priority-badge";
import { ProgressBar } from "@/components/progress-bar";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { EmptyState, ListSkeleton, LoadError } from "@/components/workspace-states";
import { useWorkspace } from "@/components/workspace-provider";
import { api, ApiError } from "@/lib/api";
import { formatDeadline } from "@/lib/task-utils";
import type { PriorityWeights, Task } from "@/lib/types";

const FACTORS = [
  ["importance", "Importance"],
  ["urgency", "Urgency"],
  ["deadline", "Deadline risk"],
  ["impact", "Expected impact"],
  ["blocking", "Blocks other tasks"],
] as const;

function WeightsPanel({ onChanged }: { onChanged: () => void }) {
  const [data, setData] = useState<PriorityWeights | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.priorities.weights().then((w) => {
      setData(w);
      setDraft(Object.fromEntries(Object.entries(w.weights).map(([k, v]) => [k, String(Math.round(v * 100))])));
    }).catch(() => toast.error("Could not load the scoring weights"));
  }, []);

  if (!data) return null;
  const total = FACTORS.reduce((sum, [k]) => sum + (Number(draft[k]) || 0), 0);

  async function save() {
    const raw = Object.fromEntries(FACTORS.map(([k]) => [k, Number(draft[k]) || 0]));
    setSaving(true);
    try {
      const res = await api.priorities.setWeights(raw);
      setData(res);
      setDraft(Object.fromEntries(Object.entries(res.weights).map(([k, v]) => [k, String(Math.round(v * 100))])));
      toast.success("Weights saved. Scores recalculated.");
      onChanged();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save the weights");
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setSaving(true);
    try {
      const res = await api.priorities.resetWeights();
      setData(res);
      setDraft(Object.fromEntries(Object.entries(res.weights).map(([k, v]) => [k, String(Math.round(v * 100))])));
      onChanged();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 rounded-2xl border bg-card p-5 shadow-card">
      <p className="text-sm text-muted-foreground">
        Relative importance of each factor. Values are rescaled so they add up to 100%. Currently {total}.
      </p>
      <div className="grid gap-3 sm:grid-cols-5">
        {FACTORS.map(([key, label]) => (
          <div key={key} className="space-y-1.5">
            <label htmlFor={`w-${key}`} className="text-xs font-medium">{label}</label>
            <Input id={`w-${key}`} inputMode="numeric" value={draft[key] ?? ""} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <Button onClick={() => void save()} disabled={saving || total <= 0}>Save weights</Button>
        {data.is_custom && <Button variant="ghost" onClick={() => void reset()} disabled={saving}>Reset to default</Button>}
      </div>
    </div>
  );
}

export default function PrioritiesPage() {
  const { tasks, toggleComplete } = useWorkspace();
  const [ranked, setRanked] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [showWeights, setShowWeights] = useState(false);

  const load = useCallback(async () => {
    try {
      setRanked(await api.priorities.ranked());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load priorities");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reload when tasks change elsewhere
    void load();
  }, [load, tasks]);

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <p className="text-section">Calculated, never guessed</p>
          <h1 className="text-display mt-1">Priorities</h1>
        </div>
        <Button variant="outline" onClick={() => setShowWeights((v) => !v)} aria-expanded={showWeights}>
          <SlidersHorizontal /> Scoring
        </Button>
      </header>

      {showWeights && <WeightsPanel onChanged={() => void load()} />}

      {error ? (
        <LoadError message={error} />
      ) : !ranked ? (
        <ListSkeleton rows={5} />
      ) : ranked.length === 0 ? (
        <EmptyState title="Nothing to rank" body="Add some tasks and they’ll be ordered here by importance, urgency, deadline risk, impact and what they block." />
      ) : (
        <ol className="space-y-2">
          {ranked.map((t, i) => {
            const expanded = open === t.id;
            return (
              <li key={t.id} className="rounded-xl border bg-card shadow-card">
                <div className="flex items-center gap-3 px-3.5 py-3">
                  <span className="w-6 text-center text-sm tabular-nums text-muted-foreground">{i + 1}</span>
                  <Checkbox
                    aria-label={`Mark “${t.title}” as done`}
                    checked={false}
                    onCheckedChange={() => void toggleComplete(t)}
                    className="size-[18px] rounded-full"
                  />
                  <Link href={`/tasks/${t.id}`} className="min-w-0 flex-1 rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
                    <span className="block truncate text-[15px] font-medium">{t.title}</span>
                    <span className="text-xs text-muted-foreground">
                      {t.deadline ? formatDeadline(t.deadline) : "No deadline"}
                      {t.waiting_on_count > 0 && ` · waiting on ${t.waiting_on_count}`}
                    </span>
                  </Link>
                  <PriorityBadge level={t.priority_level} score={t.priority_score} manual={t.priority_override !== null} />
                  <Button variant="ghost" size="icon-sm" aria-label={expanded ? "Hide explanation" : "Why this score?"} aria-expanded={expanded} onClick={() => setOpen(expanded ? null : t.id)}>
                    <ChevronRight className={`transition-transform ${expanded ? "rotate-90" : ""}`} />
                  </Button>
                </div>
                {expanded && (
                  <div className="space-y-3 border-t px-4 py-4">
                    {t.priority_explanation && <p className="text-sm">{t.priority_explanation}</p>}
                    <ul className="space-y-2">
                      {t.priority_factors?.map((f) => (
                        <li key={f.key} className="grid grid-cols-[8.5rem_1fr_3rem] items-center gap-3 text-xs">
                          <span>{f.label}</span>
                          <ProgressBar percent={f.value} label={`${f.label} ${f.value}`} />
                          <span className="text-right tabular-nums text-muted-foreground">+{f.contribution}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
