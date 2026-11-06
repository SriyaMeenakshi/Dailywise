"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, SlidersHorizontal, Sparkles } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWorkspace } from "@/components/workspace-provider";

/** One-line capture: type, press Enter, it lands in the Inbox. Details can come later. */
export function QuickAdd({ autoFocus = false }: { autoFocus?: boolean }) {
  const { addTask, openEditor } = useWorkspace();
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const value = title.trim();
    if (!value || saving) return;
    setSaving(true);
    const created = await addTask({ title: value });
    setSaving(false);
    if (created) setTitle("");
  }

  return (
    <form onSubmit={submit} className="flex items-center gap-2" role="search" aria-label="Quick add task">
      <div className="relative flex-1">
        <Plus className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Add a task and press Enter…"
          aria-label="Task title"
          maxLength={300}
          autoFocus={autoFocus}
          className="h-11 bg-card pl-9 text-[15px]"
        />
      </div>
      <Link href="/capture" className={buttonVariants({ variant: "outline", className: "h-11 px-3" })} aria-label="Capture with AI">
        <Sparkles className="text-clay" /> <span className="hidden sm:inline">AI capture</span>
      </Link>
      <Button type="button" variant="outline" className="h-11 px-3" onClick={() => openEditor(null)}>
        <SlidersHorizontal /> <span className="hidden sm:inline">Details</span>
        <span className="sr-only sm:hidden">Add with details</span>
      </Button>
    </form>
  );
}
