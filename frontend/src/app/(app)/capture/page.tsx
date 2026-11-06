"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Sparkles } from "lucide-react";
import Link from "next/link";
import { AIUsage, useAIStatus } from "@/components/ai-usage";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { useWorkspace } from "@/components/workspace-provider";
import { api, ApiError } from "@/lib/api";
import { fromLocalInput, toLocalInput } from "@/lib/task-utils";
import type { SuggestedTask } from "@/lib/types";

const MAX_CHARS = 4000;
const EXAMPLE =
  "I need to complete my DBMS assignment by Friday, study two chapters of NLP and finish my project API this week.";

interface Row {
  include: boolean;
  title: string;
  description: string;
  category_id: string;
  deadline: string; // datetime-local value
  estimate: string;
  expected_outcome: string;
  suggestedEstimate: boolean;
  dateOnly: boolean;
}

const toRow = (t: SuggestedTask): Row => ({
  include: true,
  title: t.title,
  description: t.description ?? "",
  category_id: t.category_id ?? "",
  deadline: toLocalInput(t.deadline),
  estimate: t.estimated_minutes ? String(t.estimated_minutes) : "",
  expected_outcome: t.expected_outcome ?? "",
  suggestedEstimate: t.estimated_minutes !== null,
  dateOnly: t.deadline !== null && !t.deadline_has_time,
});

export default function CapturePage() {
  const router = useRouter();
  const { categories, addTask } = useWorkspace();
  const { status, refresh } = useAIStatus();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [meta, setMeta] = useState<{ cached: boolean; removed: boolean } | null>(null);
  const [saving, setSaving] = useState(false);

  async function analyse(force = false) {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.ai.parseTasks(text, -new Date().getTimezoneOffset(), force);
      setRows(res.tasks.map(toRow));
      setQuestions(res.questions);
      setMeta({ cached: res.cached, removed: res.deadlines_removed });
      if (res.tasks.length === 0) setError("No tasks were found in that note. Try adding more detail.");
    } catch (e) {
      setRows(null);
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  const update = (i: number, patch: Partial<Row>) => setRows((prev) => prev && prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const chosen = rows?.filter((r) => r.include && r.title.trim()) ?? [];
  const invalidEstimate = (r: Row) => r.estimate.trim() !== "" && !/^\d+$/.test(r.estimate.trim());

  async function save() {
    if (!rows || chosen.length === 0 || chosen.some(invalidEstimate)) return;
    setSaving(true);
    let created = 0;
    const failed: Row[] = [];
    for (const r of chosen) {
      const task = await addTask({
        title: r.title.trim(),
        description: r.description.trim() || null,
        category_id: r.category_id || null,
        deadline: fromLocalInput(r.deadline),
        estimated_minutes: r.estimate.trim() ? Number(r.estimate) : null,
        expected_outcome: r.expected_outcome.trim() || null,
        status: "not_started",
      });
      if (task) created += 1;
      else failed.push(r);
    }
    setSaving(false);
    if (failed.length === 0) {
      toast.success(`Added ${created} ${created === 1 ? "task" : "tasks"}`);
      router.push("/tasks");
    } else {
      // Keep only what failed so retrying can't create duplicates of what was saved.
      setRows(failed);
      if (created > 0) toast.warning(`Added ${created} of ${chosen.length}. The rest are still here to retry.`);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href="/tasks" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Tasks
        </Link>
        <h1 className="text-display mt-3">Capture with AI</h1>
        <p className="mt-2 max-w-xl text-muted-foreground">
          Write what’s on your mind. Daywise suggests separate tasks, and nothing is saved until you review it.
        </p>
      </div>

      <AIUsage status={status} />

      <section className="space-y-3">
        <label htmlFor="note" className="text-sm font-medium">
          What do you need to do?
        </label>
        <Textarea
          id="note"
          rows={5}
          value={text}
          maxLength={MAX_CHARS}
          onChange={(e) => setText(e.target.value)}
          placeholder={EXAMPLE}
          disabled={status !== null && !status.configured}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs tabular-nums text-muted-foreground">
            {text.length}/{MAX_CHARS}
          </span>
          <div className="flex gap-2">
            {!text && (
              <Button type="button" variant="ghost" onClick={() => setText(EXAMPLE)}>
                Try an example
              </Button>
            )}
            <Button onClick={() => void analyse()} disabled={busy || !text.trim() || (status !== null && !status.configured)}>
              <Sparkles /> {busy ? "Reading your note…" : "Find tasks"}
            </Button>
          </div>
        </div>
      </section>

      {error && (
        <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {rows && rows.length > 0 && (
        <section className="space-y-4" aria-label="Review suggested tasks">
          <div className="flex items-end justify-between gap-3">
            <h2 className="text-title">Review</h2>
            <p className="text-xs text-muted-foreground">
              {meta?.cached ? "Reused a previous answer: no AI credit used." : "Check everything, edit freely, untick what you don’t want."}
            </p>
          </div>

          {meta?.removed && (
            <p role="status" className="rounded-xl border border-amber/40 bg-amber-soft px-4 py-3 text-sm">
              Some suggested deadlines were removed because your note didn’t mention dates. Add them below if you want them.
            </p>
          )}
          {questions.length > 0 && (
            <div role="status" className="rounded-xl border bg-card px-4 py-3 text-sm shadow-card">
              <p className="font-medium">A few things the AI wasn’t sure about</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-muted-foreground">
                {questions.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-muted-foreground">Edit your note and run it again, or just fill in the details below.</p>
            </div>
          )}

          <ul className="space-y-3">
            {rows.map((r, i) => (
              <li key={i} className={`rounded-2xl border bg-card p-4 shadow-card transition-opacity ${r.include ? "" : "opacity-50"}`}>
                <div className="flex items-start gap-3">
                  <Checkbox aria-label={`Include “${r.title}”`} checked={r.include} onCheckedChange={(v) => update(i, { include: Boolean(v) })} className="mt-2.5" />
                  <div className="min-w-0 flex-1 space-y-3">
                    <Input aria-label="Task title" value={r.title} maxLength={300} onChange={(e) => update(i, { title: e.target.value })} aria-invalid={!r.title.trim()} />
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground" htmlFor={`cat-${i}`}>Category</label>
                        <NativeSelect id={`cat-${i}`} value={r.category_id} onChange={(e) => update(i, { category_id: e.target.value })}>
                          <option value="">None</option>
                          {categories.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </NativeSelect>
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground" htmlFor={`dl-${i}`}>
                          Deadline{r.dateOnly && r.deadline ? " (end of day)" : ""}
                        </label>
                        <Input id={`dl-${i}`} type="datetime-local" value={r.deadline} onChange={(e) => update(i, { deadline: e.target.value, dateOnly: false })} />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground" htmlFor={`est-${i}`}>
                          Estimate (min){r.suggestedEstimate && r.estimate ? " · AI guess" : ""}
                        </label>
                        <Input id={`est-${i}`} inputMode="numeric" value={r.estimate} onChange={(e) => update(i, { estimate: e.target.value, suggestedEstimate: false })} aria-invalid={invalidEstimate(r)} />
                      </div>
                    </div>
                    {r.expected_outcome && <p className="text-xs text-muted-foreground">Done looks like: {r.expected_outcome}</p>}
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <div className="sticky bottom-20 flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-card/95 p-3 shadow-raised backdrop-blur md:bottom-4">
            <Button variant="ghost" onClick={() => void analyse(true)} disabled={busy} title="Ask the AI again (uses one request)">
              Try again
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setRows(null)}>
                Discard
              </Button>
              <Button onClick={() => void save()} disabled={saving || chosen.length === 0 || chosen.some(invalidEstimate)}>
                {saving ? "Saving…" : `Add ${chosen.length} ${chosen.length === 1 ? "task" : "tasks"}`}
              </Button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
