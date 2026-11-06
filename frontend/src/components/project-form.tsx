"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { fromLocalInput, toLocalInput } from "@/lib/task-utils";
import { PROJECT_STATUS_LABELS, type Project, type ProjectStatus } from "@/lib/types";

const schema = z.object({
  name: z.string().trim().min(1, "Give the project a name").max(200, "Keep the name under 200 characters"),
  objective: z.string().max(5000),
  deadline: z.string(),
  status: z.enum(["active", "on_hold", "completed", "archived"]),
});
type Values = z.infer<typeof schema>;

export interface ProjectPayload {
  name: string;
  objective: string | null;
  deadline: string | null;
  status: ProjectStatus;
}

function Form({ project, onSubmit, onCancel }: { project: Project | null; onSubmit: (p: ProjectPayload) => Promise<boolean>; onCancel: () => void }) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: project?.name ?? "",
      objective: project?.objective ?? "",
      deadline: toLocalInput(project?.deadline),
      status: project?.status ?? "active",
    },
  });

  async function submit(v: Values) {
    const ok = await onSubmit({
      name: v.name.trim(),
      objective: v.objective.trim() || null,
      deadline: fromLocalInput(v.deadline),
      status: v.status,
    });
    if (ok) onCancel();
  }

  return (
    <form onSubmit={handleSubmit(submit)} noValidate className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 space-y-5 overflow-y-auto px-4 pb-4">
        <div className="space-y-1.5">
          <Label htmlFor="p-name">Name</Label>
          <Input id="p-name" autoFocus placeholder="e.g. Final-year capstone" aria-invalid={!!errors.name} {...register("name")} />
          {errors.name && <p role="alert" className="text-xs text-destructive">{errors.name.message}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-objective">Objective</Label>
          <Textarea id="p-objective" rows={3} placeholder="What does success look like?" {...register("objective")} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="p-deadline">Deadline</Label>
            <Input id="p-deadline" type="datetime-local" {...register("deadline")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="p-status">Status</Label>
            <NativeSelect id="p-status" {...register("status")}>
              {(Object.keys(PROJECT_STATUS_LABELS) as ProjectStatus[]).map((s) => (
                <option key={s} value={s}>
                  {PROJECT_STATUS_LABELS[s]}
                </option>
              ))}
            </NativeSelect>
          </div>
        </div>
      </div>
      <div className="flex justify-end gap-2 border-t px-4 py-3">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : project ? "Save changes" : "Create project"}
        </Button>
      </div>
    </form>
  );
}

export function ProjectSheet({
  open,
  project,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  project: Project | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: ProjectPayload) => Promise<boolean>;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-md">
        <SheetHeader className="p-4 pr-12">
          <SheetTitle className="text-title">{project ? "Edit project" : "New project"}</SheetTitle>
          <SheetDescription>{project ? "Update the project details." : "Add phases and tasks after creating it."}</SheetDescription>
        </SheetHeader>
        <Form key={project?.id ?? "new"} project={project} onSubmit={onSubmit} onCancel={() => onOpenChange(false)} />
      </SheetContent>
    </Sheet>
  );
}
