import { getSupabase } from "@/lib/supabase/client";
import type {
  AIStatus,
  Analytics,
  Review,
  ReviewText,
  Block,
  Breakdown,
  BreakdownResponse,
  Category,
  ParseResponse,
  Plan,
  PlannerPrefs,
  Me,
  Phase,
  PriorityWeights,
  Project,
  Subtask,
  Task,
  TaskInput,
  TaskLog,
  TaskPatch,
  TaskStatus,
} from "@/lib/types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "");
  return "Something went wrong";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await getSupabase().auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new ApiError("You are signed out. Please sign in again.", 401);

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError("Cannot reach the Daywise server. Check your connection and try again.", 0);
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(describe(body?.detail), res.status);
  return body as T;
}

export interface TaskQuery {
  status?: TaskStatus[];
  category_id?: string;
  project_id?: string;
  q?: string;
  sort?: string;
  order?: "asc" | "desc";
}

export const api = {
  me: () => request<Me>("/me"),
  categories: {
    list: () => request<Category[]>("/categories"),
    create: (body: { name: string; color?: string }) =>
      request<Category>("/categories", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Partial<Pick<Category, "name" | "color">>) =>
      request<Category>(`/categories/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    remove: (id: string) => request<void>(`/categories/${id}`, { method: "DELETE" }),
  },
  tasks: {
    list: (query: TaskQuery = {}) => {
      const params = new URLSearchParams();
      query.status?.forEach((s) => params.append("status", s));
      if (query.category_id) params.set("category_id", query.category_id);
      if (query.project_id) params.set("project_id", query.project_id);
      if (query.q) params.set("q", query.q);
      if (query.sort) params.set("sort", query.sort);
      if (query.order) params.set("order", query.order);
      params.set("limit", "200");
      return request<Task[]>(`/tasks?${params}`);
    },
    create: (body: TaskInput) => request<Task>("/tasks", { method: "POST", body: JSON.stringify(body) }),
    get: (id: string) => request<Task>(`/tasks/${id}`),
    update: (id: string, body: TaskPatch) =>
      request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    remove: (id: string) => request<void>(`/tasks/${id}`, { method: "DELETE" }),
    subtasks: {
      list: (taskId: string) => request<Subtask[]>(`/tasks/${taskId}/subtasks`),
      create: (taskId: string, body: { title: string; estimated_minutes?: number | null }) =>
        request<Subtask>(`/tasks/${taskId}/subtasks`, { method: "POST", body: JSON.stringify(body) }),
    },
    addDependency: (taskId: string, dependsOnId: string) =>
      request<Task>(`/tasks/${taskId}/dependencies`, {
        method: "POST",
        body: JSON.stringify({ depends_on_id: dependsOnId }),
      }),
    removeDependency: (taskId: string, dependsOnId: string) =>
      request<Task>(`/tasks/${taskId}/dependencies/${dependsOnId}`, { method: "DELETE" }),
    history: (taskId: string) => request<TaskLog[]>(`/tasks/${taskId}/history`),
  },
  subtasks: {
    update: (id: string, body: Partial<Pick<Subtask, "title" | "done" | "estimated_minutes">>) =>
      request<Subtask>(`/subtasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    remove: (id: string) => request<void>(`/subtasks/${id}`, { method: "DELETE" }),
  },
  projects: {
    list: () => request<Project[]>("/projects"),
    get: (id: string) => request<Project>(`/projects/${id}`),
    create: (body: { name: string; objective?: string | null; deadline?: string | null }) =>
      request<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Partial<Pick<Project, "name" | "objective" | "deadline" | "status">>) =>
      request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    remove: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
    addPhase: (id: string, name: string) =>
      request<Phase>(`/projects/${id}/phases`, { method: "POST", body: JSON.stringify({ name }) }),
  },
  phases: {
    update: (id: string, body: { name?: string }) =>
      request<Phase>(`/phases/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    remove: (id: string) => request<void>(`/phases/${id}`, { method: "DELETE" }),
  },
  ai: {
    status: () => request<AIStatus>("/ai/status"),
    parseTasks: (text: string, utcOffsetMinutes: number, force = false) =>
      request<ParseResponse>("/ai/parse-tasks", {
        method: "POST",
        body: JSON.stringify({ text, utc_offset_minutes: utcOffsetMinutes, force }),
      }),
    decompose: (goal: string, context: string, force = false) =>
      request<BreakdownResponse>("/ai/decompose-project", {
        method: "POST",
        body: JSON.stringify({ goal, context, force }),
      }),
    applyBreakdown: (body: Breakdown & { project_id?: string | null; deadline?: string | null }) =>
      request<{ project_id: string; phases_created: number; tasks_created: number }>("/ai/decompose-project/apply", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
  plan: {
    get: (date: string) => request<Plan>(`/plan?date=${date}`),
    generate: (date: string, utcOffsetMinutes: number, startAfterMin?: number) =>
      request<Plan>("/plan/generate", {
        method: "POST",
        body: JSON.stringify({ date, utc_offset_minutes: utcOffsetMinutes, start_after_min: startAfterMin ?? null }),
      }),
    addBlock: (body: { date: string; title: string; start_min: number; end_min: number }) =>
      request<Block>("/plan/blocks", { method: "POST", body: JSON.stringify(body) }),
    updateBlock: (id: string, body: { start_min?: number; end_min?: number; done?: boolean }) =>
      request<Block>(`/plan/blocks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    move: (id: string, direction: "up" | "down") =>
      request<Block[]>(`/plan/blocks/${id}/move`, { method: "POST", body: JSON.stringify({ direction }) }),
    postpone: (id: string) => request<Block>(`/plan/blocks/${id}/postpone`, { method: "POST", body: "{}" }),
    removeBlock: (id: string) => request<void>(`/plan/blocks/${id}`, { method: "DELETE" }),
    prefs: () => request<PlannerPrefs>("/preferences/planner"),
    setPrefs: (body: PlannerPrefs) =>
      request<PlannerPrefs>("/preferences/planner", { method: "PUT", body: JSON.stringify(body) }),
  },
  insights: {
    analytics: (days: number, utcOffsetMinutes: number) =>
      request<Analytics>(`/analytics?days=${days}&utc_offset_minutes=${utcOffsetMinutes}`),
    review: (date: string, utcOffsetMinutes: number) =>
      request<Review>(`/reviews/${date}?utc_offset_minutes=${utcOffsetMinutes}`),
    saveReview: (date: string, utcOffsetMinutes: number, body: ReviewText) =>
      request<Review>(`/reviews/${date}?utc_offset_minutes=${utcOffsetMinutes}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
  },
  priorities: {
    ranked: () => request<Task[]>("/priorities"),
    weights: () => request<PriorityWeights>("/preferences/priority-weights"),
    setWeights: (weights: Record<string, number>) =>
      request<PriorityWeights>("/preferences/priority-weights", { method: "PUT", body: JSON.stringify(weights) }),
    resetWeights: () => request<PriorityWeights>("/preferences/priority-weights", { method: "DELETE" }),
  },
};
