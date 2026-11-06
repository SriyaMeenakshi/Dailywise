"use client";

import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useWorkspace } from "@/components/workspace-provider";
import { api } from "@/lib/api";
import { fromLocalInput, toLocalInput } from "@/lib/task-utils";
import {
  ENERGY_LABELS,
  ENERGY_LEVELS,
  RECURRENCES,
  RECURRENCE_LABELS,
  STATUS_LABELS,
  TASK_STATUSES,
  type Phase,
  type Task,
  type TaskInput,
} from "@/lib/types";

const MAX_MINUTES = 60 * 24 * 14;
const minutes = (label: string) =>
  z
    .string()
    .trim()
    .refine((v) => v === "" || (/^\d+$/.test(v) && Number(v) > 0 && Number(v) <= MAX_MINUTES), {
      message: `${label} must be a whole number of minutes`,
    });

const schema = z.object({
  title: z.string().trim().min(1, "Give the task a title").max(300, "Keep the title under 300 characters"),
  description: z.string().max(10_000),
  category_id: z.string(),
  project_id: z.string(),
  phase_id: z.string(),
  impact: z.string(),
  deadline: z.string(),
  estimated_minutes: minutes("Estimate"),
  actual_minutes: z
    .string()
    .trim()
    .refine((v) => v === "" || (/^\d+$/.test(v) && Number(v) <= MAX_MINUTES), {
      message: "Actual time must be a whole number of minutes",
    }),
  importance: z.string(),
  urgency: z.string(),
  energy: z.enum(ENERGY_LEVELS),
  status: z.enum(TASK_STATUSES),
  recurrence: z.enum(RECURRENCES),
  expected_outcome: z.string().max(2_000),
  notes: z.string().max(10_000),
});
type FormValues = z.infer<typeof schema>;

const LEVELS = [
  ["1", "1 · Minimal"],
  ["2", "2 · Low"],
  ["3", "3 · Moderate"],
  ["4", "4 · High"],
  ["5", "5 · Critical"],
] as const;

const defaults = (task: Task | null, preset?: Partial<TaskInput>): FormValues => ({
  title: task?.title ?? "",
  description: task?.description ?? "",
  category_id: task?.category_id ?? "",
  project_id: task?.project_id ?? preset?.project_id ?? "",
  phase_id: task?.phase_id ?? preset?.phase_id ?? "",
  impact: String(task?.impact ?? 3),
  deadline: toLocalInput(task?.deadline),
  estimated_minutes: task?.estimated_minutes?.toString() ?? "",
  actual_minutes: task?.actual_minutes?.toString() ?? "",
  importance: String(task?.importance ?? 3),
  urgency: String(task?.urgency ?? 3),
  energy: task?.energy ?? "medium",
  status: task?.status ?? "not_started",
  recurrence: task?.recurrence ?? "none",
  expected_outcome: task?.expected_outcome ?? "",
  notes: task?.notes ?? "",
});

function toPayload(v: FormValues): TaskInput {
  const optional = (s: string) => (s.trim() === "" ? null : s.trim());
  return {
    title: v.title.trim(),
    description: optional(v.description),
    category_id: v.category_id || null,
    project_id: v.project_id || null,
    phase_id: v.project_id ? v.phase_id || null : null,
    impact: Number(v.impact),
    deadline: fromLocalInput(v.deadline),
    estimated_minutes: v.estimated_minutes.trim() ? Number(v.estimated_minutes) : null,
    actual_minutes: v.actual_minutes.trim() ? Number(v.actual_minutes) : null,
    importance: Number(v.importance),
    urgency: Number(v.urgency),
    energy: v.energy,
    status: v.status,
    recurrence: v.recurrence,
    expected_outcome: optional(v.expected_outcome),
    notes: optional(v.notes),
  };
}

function Field({ label, htmlFor, error, children, hint }: { label: string; htmlFor: string; error?: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

function TaskForm({ task, preset }: { task: Task | null; preset?: Partial<TaskInput> }) {
  const { categories, projects, addTask, updateTask, closeEditor, createCategory } = useWorkspace();
  const [addingCategory, setAddingCategory] = useState(false);
  const [newCategory, setNewCategory] = useState("");
  const [loaded, setLoaded] = useState<{ projectId: string; phases: Phase[] } | null>(null);
  const {
    register,
    handleSubmit,
    setValue,
    getValues,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: defaults(task, preset) });

  const projectId = useWatch({ control, name: "project_id" });
  useEffect(() => {
    let cancelled = false;
    if (!projectId) return;
    api.projects
      .get(projectId)
      .then((p) => !cancelled && setLoaded({ projectId, phases: p.phases }))
      .catch(() => !cancelled && setLoaded({ projectId, phases: [] }));
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const phases = loaded && loaded.projectId === projectId ? loaded.phases : [];

  // Runs after the <option>s exist in the DOM (so the select can show the value) and only once the
  // phases for the *current* project have loaded (so a preset isn't wiped while they're loading).
  useEffect(() => {
    if (!loaded || loaded.projectId !== projectId) return;
    const current = getValues("phase_id");
    if (current) setValue("phase_id", loaded.phases.some((ph) => ph.id === current) ? current : "");
  }, [loaded, projectId, getValues, setValue]);

  async function onSubmit(values: FormValues) {
    const payload = toPayload(values);
    if (task) {
      if (await updateTask(task.id, payload)) closeEditor();
    } else if (await addTask(payload)) closeEditor();
  }

  async function saveCategory() {
    const name = newCategory.trim();
    if (!name) return;
    const created = await createCategory(name);
    if (created) {
      setValue("category_id", created.id);
      setNewCategory("");
      setAddingCategory(false);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col" noValidate>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 pb-4">
        <Field label="Title" htmlFor="title" error={errors.title?.message}>
          <Input id="title" autoFocus placeholder="What needs to get done?" aria-invalid={!!errors.title} {...register("title")} />
        </Field>
        <Field label="Description" htmlFor="description" error={errors.description?.message}>
          <Textarea id="description" rows={3} placeholder="Optional context" {...register("description")} />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Category" htmlFor="category_id">
            <NativeSelect id="category_id" {...register("category_id")}>
              <option value="">No category</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </NativeSelect>
            {addingCategory ? (
              <div className="flex gap-2 pt-1">
                <Input
                  aria-label="New category name"
                  value={newCategory}
                  maxLength={60}
                  onChange={(e) => setNewCategory(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void saveCategory();
                    }
                  }}
                  placeholder="Category name"
                  autoFocus
                />
                <Button type="button" variant="secondary" onClick={() => void saveCategory()}>
                  Add
                </Button>
              </div>
            ) : (
              <button type="button" onClick={() => setAddingCategory(true)} className="inline-flex items-center gap-1 pt-1 text-xs text-muted-foreground hover:text-foreground">
                <Plus className="size-3" /> New category
              </button>
            )}
          </Field>
          <Field label="Project" htmlFor="project_id">
            <NativeSelect id="project_id" {...register("project_id")}>
              <option value="">No project</option>
              {projects
                .filter((p) => p.status !== "archived" || p.id === task?.project_id)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </NativeSelect>
          </Field>
          {/* Not `disabled`: React Hook Form drops the value of disabled fields, which would wipe a preset phase. */}
          {projectId && (
            <Field label="Phase" htmlFor="phase_id" hint={phases.length === 0 ? "This project has no phases yet." : undefined}>
              <NativeSelect id="phase_id" {...register("phase_id")}>
                <option value="">No phase</option>
                {phases.map((ph) => (
                  <option key={ph.id} value={ph.id}>
                    {ph.name}
                  </option>
                ))}
              </NativeSelect>
            </Field>
          )}
          <Field label="Status" htmlFor="status">
            <NativeSelect id="status" {...register("status")}>
              {TASK_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="Deadline" htmlFor="deadline" error={errors.deadline?.message}>
            <Input id="deadline" type="datetime-local" {...register("deadline")} />
          </Field>
          <Field label="Estimated time (min)" htmlFor="estimated_minutes" error={errors.estimated_minutes?.message}>
            <Input id="estimated_minutes" inputMode="numeric" placeholder="e.g. 45" aria-invalid={!!errors.estimated_minutes} {...register("estimated_minutes")} />
          </Field>
        </div>

        <details className="group rounded-xl border bg-card/50">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-3.5 py-3 text-sm font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50 [&::-webkit-details-marker]:hidden">
            <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden />
            More details
            <span className="text-xs font-normal text-muted-foreground">importance, energy, recurrence, notes</span>
          </summary>
          <div className="grid grid-cols-1 gap-4 border-t px-3.5 py-4 sm:grid-cols-2">
            <Field label="Importance" htmlFor="importance">
              <NativeSelect id="importance" {...register("importance")}>
                {LEVELS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Urgency" htmlFor="urgency">
              <NativeSelect id="urgency" {...register("urgency")}>
                {LEVELS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Expected impact" htmlFor="impact" hint="How much does finishing this move things forward?">
              <NativeSelect id="impact" {...register("impact")}>
                {LEVELS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Energy needed" htmlFor="energy">
              <NativeSelect id="energy" {...register("energy")}>
                {ENERGY_LEVELS.map((e) => (
                  <option key={e} value={e}>
                    {ENERGY_LABELS[e]}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Repeats" htmlFor="recurrence">
              <NativeSelect id="recurrence" {...register("recurrence")}>
                {RECURRENCES.map((r) => (
                  <option key={r} value={r}>
                    {RECURRENCE_LABELS[r]}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Actual time (min)" htmlFor="actual_minutes" error={errors.actual_minutes?.message}>
              <Input id="actual_minutes" inputMode="numeric" aria-invalid={!!errors.actual_minutes} {...register("actual_minutes")} />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Expected outcome" htmlFor="expected_outcome" hint="What does “done” look like?">
                <Textarea id="expected_outcome" rows={2} {...register("expected_outcome")} />
              </Field>
            </div>
            <div className="sm:col-span-2">
              <Field label="Notes" htmlFor="notes">
                <Textarea id="notes" rows={3} {...register("notes")} />
              </Field>
            </div>
          </div>
        </details>
      </div>
      <div className="flex items-center justify-end gap-2 border-t bg-popover px-4 py-3">
        <Button type="button" variant="ghost" onClick={closeEditor}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : task ? "Save changes" : "Create task"}
        </Button>
      </div>
    </form>
  );
}

export function TaskEditor() {
  const { editor, closeEditor } = useWorkspace();
  return (
    <Sheet open={editor.open} onOpenChange={(open) => !open && closeEditor()}>
      <SheetContent className="w-full gap-0 sm:max-w-lg">
        <SheetHeader className="p-4 pr-12">
          <SheetTitle className="text-title">{editor.task ? "Edit task" : "New task"}</SheetTitle>
          <SheetDescription>{editor.task ? "Update any detail." : "Only the title is required."}</SheetDescription>
        </SheetHeader>
        <TaskForm key={editor.task?.id ?? "new"} task={editor.task} preset={editor.preset} />
      </SheetContent>
    </Sheet>
  );
}
