"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, CalendarDays, CheckSquare, FolderKanban, LayoutDashboard, ListOrdered, LogOut, Plus } from "lucide-react";
import { cn } from "cn";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/logo";
import { TaskEditor } from "@/components/task-editor";
import { useWorkspace } from "@/components/workspace-provider";
import { getSupabase } from "@/lib/supabase/client";

const NAV = [
  { href: "/dashboard", label: "Today", icon: LayoutDashboard },
  { href: "/tasks", label: "Tasks", icon: CheckSquare },
  { href: "/planner", label: "Plan", icon: CalendarDays },
  { href: "/priorities", label: "Priorities", icon: ListOrdered },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/insights", label: "Insights", icon: BarChart3 },
] as const;

function isTyping(el: EventTarget | null) {
  return el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { me, openEditor, editor } = useWorkspace();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "c" && !e.metaKey && !e.ctrlKey && !e.altKey && !isTyping(e.target) && !editor.open) {
        e.preventDefault();
        openEditor(null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openEditor, editor.open]);

  async function signOut() {
    await getSupabase().auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  const link = (item: (typeof NAV)[number], layout: "side" | "bottom") => {
    const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
    return (
      <Link
        key={item.href}
        href={item.href}
        aria-current={active ? "page" : undefined}
        className={cn(
          "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          layout === "side"
            ? "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
            : "flex flex-1 flex-col items-center gap-1 py-2 text-[11px] font-medium",
          active ? (layout === "side" ? "bg-card text-foreground shadow-card" : "text-foreground") : "text-muted-foreground hover:text-foreground",
        )}
      >
        <item.icon className="size-4" aria-hidden />
        {item.label}
      </Link>
    );
  };

  return (
    <div className="flex min-h-dvh">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r bg-sidebar px-3 py-5 md:flex">
        <Logo href="/dashboard" className="px-3" />
        <Button className="mt-6 h-9 justify-start gap-2 px-3" onClick={() => openEditor(null)}>
          <Plus /> New task
          <kbd className="ml-auto rounded bg-primary-foreground/15 px-1.5 text-[11px]">C</kbd>
        </Button>
        <nav aria-label="Main" className="mt-5 flex flex-col gap-1">
          {NAV.map((n) => link(n, "side"))}
        </nav>
        <div className="mt-auto border-t pt-4">
          <p className="truncate px-3 text-xs text-muted-foreground" title={me?.email ?? undefined}>
            {me?.email ?? " "}
          </p>
          <Button variant="ghost" className="mt-1 w-full justify-start gap-2 px-3 text-muted-foreground" onClick={signOut}>
            <LogOut /> Sign out
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b bg-background/90 px-4 py-3 backdrop-blur md:hidden">
          <Logo href="/dashboard" />
          <Button variant="ghost" size="icon" aria-label="Sign out" onClick={signOut}>
            <LogOut />
          </Button>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto outline-none w-full max-w-4xl flex-1 px-4 pt-6 pb-28 sm:px-8 md:pt-10 md:pb-16">
          {children}
        </main>
        <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 flex items-center border-t bg-background/95 px-2 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
          {link(NAV[0], "bottom")}
          {link(NAV[1], "bottom")}
          <button
            type="button"
            onClick={() => openEditor(null)}
            aria-label="New task"
            className="-mt-5 grid size-12 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground shadow-raised outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <Plus className="size-5" />
          </button>
          {link(NAV[2], "bottom")}
          {link(NAV[4], "bottom")}
        </nav>
      </div>
      <TaskEditor />
    </div>
  );
}
