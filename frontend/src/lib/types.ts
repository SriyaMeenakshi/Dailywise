export const TASK_STATUSES = ["inbox", "not_started", "in_progress", "completed", "blocked", "archived"] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const ENERGY_LEVELS = ["low", "medium", "high"] as const;
export type Energy = (typeof ENERGY_LEVELS)[number];

export const RECURRENCES = ["none", "daily", "weekdays", "weekly", "monthly"] as const;
export type Recurrence = (typeof RECURRENCES)[number];

export const STATUS_LABELS: Record<TaskStatus, string> = {
  inbox: "Inbox",
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
  blocked: "Blocked",
  archived: "Archived",
};

export const RECURRENCE_LABELS: Record<Recurrence, string> = {
  none: "Does not repeat",
  daily: "Daily",
  weekdays: "Weekdays",
  weekly: "Weekly",
  monthly: "Monthly",
};

export const ENERGY_LABELS: Record<Energy, string> = { low: "Low", medium: "Medium", high: "High" };

export interface Category {
  id: string;
  name: string;
  color: string;
  sort_order: number;
}

export type PriorityLevel = "low" | "medium" | "high" | "critical";

export interface PriorityFactor {
  key: string;
  label: string;
  value: number;
  weight: number;
  contribution: number;
}

export interface Progress {
  percent: number;
  total_minutes: number;
  done_minutes: number;
  remaining_minutes: number;
  tasks_total: number;
  tasks_done: number;
  unestimated_tasks: number;
}

export type ProjectStatus = "active" | "on_hold" | "completed" | "archived";

export interface Phase {
  id: string;
  project_id: string;
  name: string;
  sort_order: number;
  milestone: string | null;
  progress: Progress | null;
  earliest_deadline: string | null;
  latest_deadline: string | null;
}

export interface Project {
  id: string;
  name: string;
  objective: string | null;
  status: ProjectStatus;
  deadline: string | null;
  created_at: string;
  updated_at: string;
  progress: Progress | null;
  phases: Phase[];
  unphased_progress: Progress | null;
}

export interface Subtask {
  id: string;
  task_id: string;
  title: string;
  estimated_minutes: number | null;
  done: boolean;
  sort_order: number;
}

export interface TaskLog {
  id: string;
  action: string;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface PriorityWeights {
  weights: Record<string, number>;
  defaults: Record<string, number>;
  is_custom: boolean;
}

// ── AI ────────────────────────────────────────────────────────────────────────
export interface AIStatus {
  configured: boolean;
  model: string | null;
  complex_model: string | null;
  requests_today: number;
  request_limit: number;
  tokens_today: number;
  token_limit: number;
  cost_today_usd: number;
  cached_today: number;
  cost_tracking: boolean;
}

export interface SuggestedTask {
  title: string;
  description: string | null;
  category_id: string | null;
  category_name: string | null;
  deadline: string | null;
  deadline_has_time: boolean;
  expected_outcome: string | null;
  estimated_minutes: number | null;
  importance: number | null;
}

export interface ParseResponse {
  tasks: SuggestedTask[];
  questions: string[];
  cached: boolean;
  model: string;
  deadlines_removed: boolean;
}

export interface PlanSubtask {
  title: string;
  estimated_minutes: number | null;
}

export interface PlanTask {
  ref: string;
  title: string;
  description: string | null;
  estimated_minutes: number | null;
  subtasks: PlanSubtask[];
  depends_on: string[];
}

export interface PlanPhase {
  name: string;
  milestone: string | null;
  tasks: PlanTask[];
}

export interface Breakdown {
  project_name: string;
  objective: string | null;
  phases: PlanPhase[];
}

export interface BreakdownResponse extends Breakdown {
  cached: boolean;
  model: string;
  truncated: boolean;
}

// ── Planner ───────────────────────────────────────────────────────────────────
export type BlockKind = "task" | "break" | "fixed" | "postponed";

export interface Block {
  id: string;
  task_id: string | null;
  plan_date: string;
  kind: BlockKind;
  title: string | null;
  start_min: number;
  end_min: number;
  pinned: boolean;
  done: boolean;
  warning: string | null;
  priority_level: PriorityLevel | null;
}

export interface Plan {
  date: string;
  window_start: number;
  window_end: number;
  break_minutes: number;
  blocks: Block[];
  unscheduled: { task_id: string; title: string; reason: string }[];
  unscheduled_total: number;
  planned_minutes: number;
  free_minutes: number;
}

export interface PlannerPrefs {
  workday_start_min: number;
  workday_end_min: number;
  break_minutes: number;
}

// ── Insights ──────────────────────────────────────────────────────────────────
export interface TaskBrief {
  id: string;
  title: string;
  deadline: string | null;
  estimated_minutes: number | null;
  actual_minutes: number | null;
  priority_level: PriorityLevel | null;
}

export interface ReviewText {
  accomplished: string;
  remaining: string;
  blockers: string;
  tomorrow_focus: string;
}

export interface Review {
  date: string;
  saved: ReviewText | null;
  facts: {
    completed: TaskBrief[];
    completed_minutes: number;
    remaining: TaskBrief[];
    blocked: TaskBrief[];
    suggested_tomorrow: TaskBrief[];
  };
}

export interface Analytics {
  days: number;
  completed: number;
  pending: number;
  overdue: number;
  blocked: number;
  completed_with_deadline: number;
  completed_on_time: number;
  daily: { date: string; completed: number; completed_minutes: number }[];
  by_category: { name: string; color: string; completed: number; pending: number }[];
  time_accuracy: { tasks: number; estimated_minutes: number; actual_minutes: number; biggest_misses: TaskBrief[] };
  projects: { id: string; name: string; percent: number; remaining_minutes: number; deadline: string | null }[];
}

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  active: "Active",
  on_hold: "On hold",
  completed: "Completed",
  archived: "Archived",
};

export interface Task {
  id: string;
  title: string;
  description: string | null;
  expected_outcome: string | null;
  notes: string | null;
  category_id: string | null;
  project_id: string | null;
  phase_id: string | null;
  importance: number;
  urgency: number;
  impact: number;
  priority_score: number;
  priority_computed: number;
  priority_override: number | null;
  priority_level: PriorityLevel;
  priority_factors: PriorityFactor[] | null;
  priority_explanation: string | null;
  dependency_ids: string[];
  waiting_on_count: number;
  energy: Energy;
  status: TaskStatus;
  recurrence: Recurrence;
  deadline: string | null;
  estimated_minutes: number | null;
  actual_minutes: number | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

type ReadOnlyTaskFields =
  | "id"
  | "completed_at"
  | "created_at"
  | "updated_at"
  | "priority_score"
  | "priority_computed"
  | "priority_level"
  | "priority_factors"
  | "priority_explanation"
  | "dependency_ids"
  | "waiting_on_count";

export type TaskInput = Partial<Omit<Task, ReadOnlyTaskFields>> & {
  title: string;
};
export type TaskPatch = Partial<TaskInput>;

export interface Me {
  id: string;
  email: string | null;
  display_name: string | null;
}
