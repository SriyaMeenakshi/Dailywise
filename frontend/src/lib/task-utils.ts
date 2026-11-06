import type { Task } from "@/lib/types";

const ACTIVE_STATUSES = new Set(["inbox", "not_started", "in_progress", "blocked"]);

export const isActive = (t: Task) => ACTIVE_STATUSES.has(t.status);
export const isDone = (t: Task) => t.status === "completed";

export function startOfDay(d: Date) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

const DAY_MS = 86_400_000;

/** Whole calendar days from today to the deadline (negative = past). */
export function daysUntil(deadline: string, now = new Date()) {
  return Math.round((startOfDay(new Date(deadline)).getTime() - startOfDay(now).getTime()) / DAY_MS);
}

export const isOverdue = (t: Task, now = new Date()) =>
  isActive(t) && t.deadline !== null && new Date(t.deadline).getTime() < now.getTime();

export const isDueToday = (t: Task, now = new Date()) =>
  isActive(t) && t.deadline !== null && daysUntil(t.deadline, now) === 0;

export function formatDeadline(deadline: string, now = new Date()) {
  const date = new Date(deadline);
  const days = daysUntil(deadline, now);
  const hasTime = date.getHours() !== 0 || date.getMinutes() !== 0;
  const time = hasTime ? date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "";
  let label: string;
  if (days === 0) label = "Today";
  else if (days === 1) label = "Tomorrow";
  else if (days === -1) label = "Yesterday";
  else if (days > 1 && days < 7) label = date.toLocaleDateString(undefined, { weekday: "long" });
  else label = date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return time ? `${label}, ${time}` : label;
}

export function formatMinutes(minutes: number) {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

/** ISO string -> value for <input type="datetime-local"> in the user's timezone. */
export function toLocalInput(iso: string | null | undefined) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export const fromLocalInput = (value: string) => (value ? new Date(value).toISOString() : null);

export function greeting(now = new Date()) {
  const h = now.getHours();
  if (h < 5) return "Still up";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

/** Sort by deadline (soonest first, none last), then importance. */
export function byUrgency(a: Task, b: Task) {
  const da = a.deadline ? new Date(a.deadline).getTime() : Infinity;
  const db = b.deadline ? new Date(b.deadline).getTime() : Infinity;
  if (da !== db) return da - db;
  return b.importance + b.urgency - (a.importance + a.urgency);
}
