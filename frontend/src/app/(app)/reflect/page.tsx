"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, ChevronLeft, ChevronRight, Wand2 } from "lucide-react";
import { PriorityBadge } from "@/components/priority-badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ListSkeleton, LoadError } from "@/components/workspace-states";
import { api, ApiError } from "@/lib/api";
import { formatDeadline, formatMinutes } from "@/lib/task-utils";
import type { Review, ReviewText, TaskBrief } from "@/lib/types";

const pad = (n: number) => String(n).padStart(2, "0");
const keyOf = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const shift = (k: string, days: number) => {
  const d = new Date(`${k}T12:00:00`);
  d.setDate(d.getDate() + days);
  return keyOf(d);
};
const offset = () => -new Date().getTimezoneOffset();
const EMPTY: ReviewText = { accomplished: "", remaining: "", blockers: "", tomorrow_focus: "" };

const bullets = (tasks: TaskBrief[]) => tasks.map((t) => `• ${t.title}`).join("\n");

const FIELDS: { key: keyof ReviewText; label: string; hint: string }[] = [
  { key: "accomplished", label: "What did I accomplish?", hint: "Wins, big or small." },
  { key: "remaining", label: "What remains?", hint: "What’s still open, and why." },
  { key: "blockers", label: "What blocked me?", hint: "Anything that slowed you down or stopped you." },
  { key: "tomorrow_focus", label: "What should I prioritise tomorrow?", hint: "One to three things." },
];

function FactList({ title, tasks, empty, extra }: { title: string; tasks: TaskBrief[]; empty: string; extra?: React.ReactNode }) {
  return (
    <section className="space-y-2" aria-label={title}>
      <h3 className="text-section">{title}{tasks.length > 0 && <span className="ml-2 tabular-nums">{tasks.length}</span>}</h3>
      {tasks.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {tasks.map((t) => (
            <li key={t.id} className="flex items-baseline justify-between gap-3">
              <Link href={`/tasks/${t.id}`} className="truncate hover:underline">{t.title}</Link>
              <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                {t.priority_level && (t.priority_level === "high" || t.priority_level === "critical") && <PriorityBadge level={t.priority_level} />}
                {t.deadline && formatDeadline(t.deadline)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {extra}
    </section>
  );
}

export default function ReflectPage() {
  const [day, setDay] = useState(() => keyOf(new Date()));
  const [review, setReview] = useState<Review | null>(null);
  const [text, setText] = useState<ReviewText>(EMPTY);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const isToday = day === keyOf(new Date());

  const load = useCallback(async () => {
    setReview(null);
    try {
      const r = await api.insights.review(day, offset());
      setReview(r);
      setText(r.saved ?? EMPTY);
      setDirty(false);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load your review");
    }
  }, [day]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reload when the day changes
    void load();
  }, [load]);

  function change(key: keyof ReviewText, value: string) {
    setText((t) => ({ ...t, [key]: value }));
    setDirty(true);
  }

  function prefill() {
    if (!review) return;
    const f = review.facts;
    setText((t) => ({
      accomplished: t.accomplished || bullets(f.completed),
      remaining: t.remaining || bullets(f.remaining),
      blockers: t.blockers || bullets(f.blocked),
      tomorrow_focus: t.tomorrow_focus || bullets(f.suggested_tomorrow.slice(0, 3)),
    }));
    setDirty(true);
  }

  async function save() {
    setSaving(true);
    try {
      const r = await api.insights.saveReview(day, offset(), text);
      setReview(r);
      setText(r.saved ?? EMPTY);
      setDirty(false);
      toast.success("Review saved");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save your review");
    } finally {
      setSaving(false);
    }
  }

  function go(delta: number) {
    if (dirty && !window.confirm("You have unsaved changes. Leave without saving?")) return;
    setDay(shift(day, delta));
  }

  return (
    <div className="space-y-8">
      <div>
        <Link href="/insights" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Insights
        </Link>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <h1 className="text-display">End-of-day review</h1>
          <div className="flex items-center gap-1" role="group" aria-label="Choose day">
            <Button variant="outline" size="icon" aria-label="Previous day" onClick={() => go(-1)}><ChevronLeft /></Button>
            <span className="min-w-40 text-center text-sm font-medium">
              {isToday ? "Today · " : ""}{new Date(`${day}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}
            </span>
            <Button variant="outline" size="icon" aria-label="Next day" disabled={isToday} onClick={() => go(1)}><ChevronRight /></Button>
          </div>
        </div>
      </div>

      {error ? (
        <LoadError message={error} />
      ) : !review ? (
        <ListSkeleton rows={4} />
      ) : (
        <div className="grid gap-8 lg:grid-cols-[1fr_1.1fr]">
          <aside className="space-y-6 rounded-2xl border bg-card p-5 shadow-card lg:self-start" aria-label="What your tasks show">
            <p className="text-sm text-muted-foreground">Pulled from your tasks. Nothing here is guessed.</p>
            <FactList
              title="Completed"
              tasks={review.facts.completed}
              empty="Nothing completed this day."
              extra={review.facts.completed_minutes > 0 && <p className="text-xs text-muted-foreground">About {formatMinutes(review.facts.completed_minutes)} of work.</p>}
            />
            <FactList title="Still open and due" tasks={review.facts.remaining} empty="Nothing overdue or due." />
            <FactList title="Blocked" tasks={review.facts.blocked} empty="Nothing is marked as blocked." />
            <FactList title="Top priorities next" tasks={review.facts.suggested_tomorrow} empty="No open tasks." />
          </aside>

          <form
            className="space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-title">Your reflection</h2>
              <Button type="button" variant="ghost" size="sm" onClick={prefill} title="Fill empty answers from the facts on the left">
                <Wand2 /> Fill from my tasks
              </Button>
            </div>
            {FIELDS.map((f) => (
              <div key={f.key} className="space-y-1.5">
                <label htmlFor={`r-${f.key}`} className="text-sm font-medium">{f.label}</label>
                <Textarea id={`r-${f.key}`} rows={4} maxLength={5000} value={text[f.key]} onChange={(e) => change(f.key, e.target.value)} />
                <p className="text-xs text-muted-foreground">{f.hint}</p>
              </div>
            ))}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={saving || !dirty}>{saving ? "Saving…" : "Save review"}</Button>
              {!dirty && review.saved && <span className="text-sm text-muted-foreground" role="status">Saved</span>}
              {dirty && <span className="text-sm text-muted-foreground" role="status">Unsaved changes</span>}
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
