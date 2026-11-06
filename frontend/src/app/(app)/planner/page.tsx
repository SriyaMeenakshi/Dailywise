"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { AlertTriangle, ArrowDown, ArrowUp, CalendarPlus, ChevronLeft, ChevronRight, Clock, Pencil, RotateCcw, SkipForward, Wand2, X } from "lucide-react";
import { PriorityBadge } from "@/components/priority-badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { ListSkeleton } from "@/components/workspace-states";
import { useWorkspace } from "@/components/workspace-provider";
import { api, ApiError } from "@/lib/api";
import { formatMinutes } from "@/lib/task-utils";
import type { Block, Plan, PlannerPrefs } from "@/lib/types";

const pad = (n: number) => String(n).padStart(2, "0");
const dateKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const fromKey = (k: string) => new Date(`${k}T12:00:00`);
const shift = (k: string, days: number) => {
  const d = fromKey(k);
  d.setDate(d.getDate() + days);
  return dateKey(d);
};
const toInput = (m: number) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
const fromInput = (v: string) => {
  const [h, m] = v.split(":").map(Number);
  return Number.isFinite(h) && Number.isFinite(m) ? h * 60 + m : NaN;
};
const fmt = (m: number) => {
  const h = Math.floor(m / 60) % 24;
  return `${h % 12 || 12}:${pad(m % 60)} ${h < 12 ? "AM" : "PM"}`;
};
const offset = () => -new Date().getTimezoneOffset();

function TimeEditor({ block, onSave, onCancel }: { block: Block; onSave: (s: number, e: number) => void; onCancel: () => void }) {
  const [start, setStart] = useState(toInput(block.start_min));
  const [end, setEnd] = useState(toInput(block.end_min));
  const s = fromInput(start);
  const e = fromInput(end);
  const ok = Number.isFinite(s) && Number.isFinite(e) && s < e;
  return (
    <form
      className="mt-2 flex flex-wrap items-center gap-2"
      onSubmit={(ev) => {
        ev.preventDefault();
        if (ok) onSave(s, e);
      }}
    >
      <Input aria-label="Start time" type="time" step={300} value={start} onChange={(ev) => setStart(ev.target.value)} className="w-32" />
      <span aria-hidden>–</span>
      <Input aria-label="End time" type="time" step={300} value={end} onChange={(ev) => setEnd(ev.target.value)} className="w-32" />
      <Button type="submit" size="sm" disabled={!ok}>Save</Button>
      <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      {!ok && <span role="alert" className="text-xs text-destructive">End must be after start</span>}
    </form>
  );
}

export default function PlannerPage() {
  const { refreshTasks, tasks } = useWorkspace();
  const [day, setDay] = useState(() => dateKey(new Date()));
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [prefs, setPrefs] = useState<PlannerPrefs | null>(null);
  const [fixed, setFixed] = useState({ title: "", start: "12:00", end: "13:00" });
  const isToday = day === dateKey(new Date());

  const load = useCallback(async () => {
    try {
      setPlan(await api.plan.get(day));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load your plan");
    }
  }, [day]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reload when the date changes
    void load();
  }, [load]);

  useEffect(() => {
    api.plan.prefs().then(setPrefs).catch(() => undefined);
  }, []);

  async function run<T>(fn: () => Promise<T>, success?: string): Promise<T | null> {
    setBusy(true);
    try {
      const out = await fn();
      if (success) toast.success(success);
      return out;
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Something went wrong");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    const now = new Date();
    const startAfter = isToday ? now.getHours() * 60 + now.getMinutes() : undefined;
    const res = await run(() => api.plan.generate(day, offset(), startAfter));
    if (res) setPlan(res);
  }

  const reload = async () => {
    await Promise.all([load(), refreshTasks()]);
  };

  async function toggleDone(b: Block) {
    if (await run(() => api.plan.updateBlock(b.id, { done: !b.done }))) await reload();
  }
  async function move(b: Block, dir: "up" | "down") {
    if (await run(() => api.plan.move(b.id, dir))) await load();
  }
  async function postpone(b: Block) {
    if (await run(() => api.plan.postpone(b.id), "Postponed. It won’t be planned again today unless you bring it back.")) await load();
  }
  async function bringBack(b: Block) {
    if (await run(() => api.plan.removeBlock(b.id))) await generate();
  }
  async function saveTime(b: Block, s: number, e: number) {
    if (await run(() => api.plan.updateBlock(b.id, { start_min: s, end_min: e }))) {
      setEditing(null);
      await load();
    }
  }
  async function removeFixed(b: Block) {
    if (await run(() => api.plan.removeBlock(b.id))) await load();
  }
  async function addFixed(e: React.FormEvent) {
    e.preventDefault();
    const s = fromInput(fixed.start);
    const en = fromInput(fixed.end);
    if (!fixed.title.trim() || !(s < en)) return toast.error("Give it a title and an end time after the start");
    if (await run(() => api.plan.addBlock({ date: day, title: fixed.title.trim(), start_min: s, end_min: en }))) {
      setFixed({ ...fixed, title: "" });
      await load();
    }
  }
  async function savePrefs(e: React.FormEvent) {
    e.preventDefault();
    if (!prefs) return;
    const saved = await run(() => api.plan.setPrefs(prefs), "Availability saved. Recalculate to apply it.");
    if (saved) setPrefs(saved);
  }

  const visible = plan?.blocks.filter((b) => b.kind !== "postponed") ?? [];
  const postponed = plan?.blocks.filter((b) => b.kind === "postponed") ?? [];
  const taskBlocks = visible.filter((b) => b.kind === "task");
  const hasPlan = visible.length > 0;
  const activeCount = tasks.filter((t) => ["inbox", "not_started", "in_progress"].includes(t.status)).length;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-section">Deterministic: no AI involved</p>
          <h1 className="text-display mt-1">Plan</h1>
        </div>
        <div className="flex items-center gap-1" role="group" aria-label="Choose day">
          <Button variant="outline" size="icon" aria-label="Previous day" onClick={() => setDay(shift(day, -1))}><ChevronLeft /></Button>
          <Button variant="outline" className="min-w-40" onClick={() => setDay(dateKey(new Date()))} aria-label="Jump to today">
            {isToday ? "Today · " : ""}{fromKey(day).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}
          </Button>
          <Button variant="outline" size="icon" aria-label="Next day" onClick={() => setDay(shift(day, 1))}><ChevronRight /></Button>
        </div>
      </header>

      {error ? (
        <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</p>
      ) : !plan ? (
        <ListSkeleton rows={4} />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-card p-4 shadow-card">
            <div className="flex gap-6 text-sm">
              <div><p className="text-section">Planned</p><p className="font-display text-2xl tabular-nums">{formatMinutes(plan.planned_minutes)}</p></div>
              <div><p className="text-section">Free</p><p className="font-display text-2xl tabular-nums">{formatMinutes(plan.free_minutes)}</p></div>
              <div className="hidden sm:block"><p className="text-section">Available</p><p className="font-display text-2xl tabular-nums">{fmt(plan.window_start)}–{fmt(plan.window_end)}</p></div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setShowSettings((v) => !v)} aria-expanded={showSettings}><Clock /> Availability</Button>
              <Button onClick={() => void generate()} disabled={busy}>
                <Wand2 /> {hasPlan ? "Recalculate" : "Plan my day"}
              </Button>
            </div>
          </div>

          {showSettings && prefs && (
            <form onSubmit={savePrefs} className="flex flex-wrap items-end gap-4 rounded-2xl border bg-card p-4 shadow-card">
              <div className="space-y-1.5"><label className="text-xs text-muted-foreground" htmlFor="ws">Day starts</label><Input id="ws" type="time" className="w-32" value={toInput(prefs.workday_start_min)} onChange={(e) => setPrefs({ ...prefs, workday_start_min: fromInput(e.target.value) })} /></div>
              <div className="space-y-1.5"><label className="text-xs text-muted-foreground" htmlFor="we">Day ends</label><Input id="we" type="time" className="w-32" value={toInput(prefs.workday_end_min)} onChange={(e) => setPrefs({ ...prefs, workday_end_min: fromInput(e.target.value) })} /></div>
              <div className="space-y-1.5"><label className="text-xs text-muted-foreground" htmlFor="wb">Break between tasks (min)</label><Input id="wb" inputMode="numeric" className="w-24" value={String(prefs.break_minutes)} onChange={(e) => setPrefs({ ...prefs, break_minutes: Number(e.target.value.replace(/\D/g, "")) || 0 })} /></div>
              <Button type="submit" variant="secondary" disabled={busy}>Save</Button>
            </form>
          )}

          {!hasPlan ? (
            <div className="flex flex-col items-center rounded-2xl border border-dashed px-6 py-12 text-center">
              <div className="grid size-11 place-items-center rounded-full bg-clay-soft text-clay"><CalendarPlus className="size-5" aria-hidden /></div>
              <h2 className="mt-4 text-lg">{activeCount === 0 ? "Nothing to plan yet" : "No plan for this day"}</h2>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                {activeCount === 0
                  ? "Add some tasks first, then Daywise fits the most important ones into your available hours."
                  : "Daywise fits your highest-priority tasks into your available hours, with breaks, and respects what depends on what."}
              </p>
              <div className="mt-5"><Button onClick={() => void generate()} disabled={busy || activeCount === 0}><Wand2 /> Plan my day</Button></div>
            </div>
          ) : (
            <ol className="space-y-2" aria-label="Schedule">
              {visible.map((b) => {
                if (b.kind === "break") {
                  return (
                    <li key={b.id} className="flex items-center gap-3 px-3 text-xs text-muted-foreground">
                      <span className="w-[5.5rem] shrink-0 tabular-nums">{fmt(b.start_min)}</span>
                      <span className="h-px flex-1 bg-border" aria-hidden /> Break · {b.end_min - b.start_min}m
                    </li>
                  );
                }
                const ti = taskBlocks.findIndex((t) => t.id === b.id);
                return (
                  <li key={b.id} className={`rounded-xl border px-3.5 py-3 shadow-card ${b.kind === "fixed" ? "border-dashed bg-muted/40" : "bg-card"} ${b.done ? "opacity-60" : ""}`}>
                    <div className="flex items-start gap-3">
                      <div className="w-[5.5rem] shrink-0 pt-0.5 text-xs tabular-nums text-muted-foreground">
                        {fmt(b.start_min)}
                        <br />
                        <span className="opacity-70">{fmt(b.end_min)}</span>
                      </div>
                      {b.kind === "task" && (
                        <Checkbox aria-label={b.done ? `Mark “${b.title}” not done` : `Mark “${b.title}” done`} checked={b.done} onCheckedChange={() => void toggleDone(b)} className="mt-0.5 size-[18px] rounded-full" />
                      )}
                      <div className="min-w-0 flex-1">
                        {b.kind === "task" && b.task_id ? (
                          <Link href={`/tasks/${b.task_id}`} className={`block truncate text-[15px] font-medium hover:underline ${b.done ? "line-through" : ""}`}>{b.title}</Link>
                        ) : (
                          <p className="truncate text-[15px] font-medium">{b.title} <span className="text-xs font-normal text-muted-foreground">· your commitment</span></p>
                        )}
                        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                          <span>{formatMinutes(b.end_min - b.start_min)}</span>
                          {b.priority_level && !b.done && <PriorityBadge level={b.priority_level} />}
                          {b.pinned && b.kind === "task" && <span title="You moved this; recalculating won’t touch it">Locked in place</span>}
                          {b.warning && (
                            <span className="inline-flex items-center gap-1 font-medium text-destructive"><AlertTriangle className="size-3.5" aria-hidden />{b.warning}</span>
                          )}
                        </p>
                        {editing === b.id && <TimeEditor block={b} onSave={(s, e) => void saveTime(b, s, e)} onCancel={() => setEditing(null)} />}
                      </div>
                      <div className="flex shrink-0 gap-0.5">
                        {b.kind === "task" && !b.done && (
                          <>
                            <Button variant="ghost" size="icon-sm" aria-label={`Move “${b.title}” earlier`} disabled={busy || ti === 0} onClick={() => void move(b, "up")}><ArrowUp /></Button>
                            <Button variant="ghost" size="icon-sm" aria-label={`Move “${b.title}” later`} disabled={busy || ti === taskBlocks.length - 1} onClick={() => void move(b, "down")}><ArrowDown /></Button>
                          </>
                        )}
                        {!b.done && <Button variant="ghost" size="icon-sm" aria-label={`Change time for “${b.title}”`} onClick={() => setEditing(editing === b.id ? null : b.id)}><Pencil /></Button>}
                        {b.kind === "task" && !b.done && <Button variant="ghost" size="icon-sm" aria-label={`Postpone “${b.title}”`} onClick={() => void postpone(b)}><SkipForward /></Button>}
                        {b.kind === "fixed" && <Button variant="ghost" size="icon-sm" aria-label={`Remove “${b.title}”`} onClick={() => void removeFixed(b)}><X /></Button>}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}

          {plan.unscheduled_total > 0 && (
            <section className="space-y-2" aria-label="Not scheduled">
              <h2 className="text-section">Didn’t fit · {plan.unscheduled_total}</h2>
              <ul className="space-y-1.5 text-sm">
                {plan.unscheduled.map((u) => (
                  <li key={u.task_id} className="flex flex-wrap items-baseline justify-between gap-x-4 rounded-lg px-1">
                    <Link href={`/tasks/${u.task_id}`} className="hover:underline">{u.title}</Link>
                    <span className="text-xs text-muted-foreground">{u.reason}</span>
                  </li>
                ))}
                {plan.unscheduled_total > plan.unscheduled.length && <li className="text-xs text-muted-foreground">…and {plan.unscheduled_total - plan.unscheduled.length} more, all lower priority.</li>}
              </ul>
            </section>
          )}

          {postponed.length > 0 && (
            <section className="space-y-2" aria-label="Postponed">
              <h2 className="text-section">Postponed · {postponed.length}</h2>
              <ul className="space-y-1.5 text-sm">
                {postponed.map((b) => (
                  <li key={b.id} className="flex items-center justify-between gap-3">
                    <span className="truncate text-muted-foreground">{b.title}</span>
                    <Button variant="ghost" size="sm" onClick={() => void bringBack(b)}><RotateCcw /> Bring back</Button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <form onSubmit={addFixed} className="space-y-2 rounded-2xl border bg-card/60 p-4" aria-label="Add a commitment">
            <h2 className="text-sm font-medium">Add something fixed <span className="font-normal text-muted-foreground">(a class, a meeting, lunch)</span></h2>
            <div className="flex flex-wrap items-center gap-2">
              <Input aria-label="Title" className="min-w-40 flex-1" placeholder="e.g. Lecture" value={fixed.title} maxLength={300} onChange={(e) => setFixed({ ...fixed, title: e.target.value })} />
              <Input aria-label="Starts" type="time" step={300} className="w-32" value={fixed.start} onChange={(e) => setFixed({ ...fixed, start: e.target.value })} />
              <span aria-hidden>–</span>
              <Input aria-label="Ends" type="time" step={300} className="w-32" value={fixed.end} onChange={(e) => setFixed({ ...fixed, end: e.target.value })} />
              <Button type="submit" variant="secondary" disabled={busy || !fixed.title.trim()}>Add</Button>
            </div>
            <p className="text-xs text-muted-foreground">Task deadlines are separate from time blocks: a task can be scheduled today and still be due later. Recalculate after adding commitments.</p>
          </form>
        </>
      )}
    </div>
  );
}
