"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import {
  TASK_STATUSES,
  type Category,
  type Me,
  type Project,
  type Task,
  type TaskInput,
  type TaskPatch,
} from "@/lib/types";

interface Workspace {
  me: Me | null;
  tasks: Task[];
  categories: Category[];
  loading: boolean;
  loadError: string | null;
  reload: () => Promise<void>;
  addTask: (input: TaskInput) => Promise<Task | null>;
  updateTask: (id: string, patch: TaskPatch) => Promise<boolean>;
  deleteTask: (id: string) => Promise<void>;
  toggleComplete: (task: Task) => Promise<void>;
  createCategory: (name: string, color?: string) => Promise<Category | null>;
  projects: Project[];
  refreshProjects: () => Promise<void>;
  refreshTasks: () => Promise<void>;
  editor: { open: boolean; task: Task | null; preset?: Partial<TaskInput> };
  openEditor: (task?: Task | null, preset?: Partial<TaskInput>) => void;
  closeEditor: () => void;
}

const Ctx = createContext<Workspace | null>(null);

export function useWorkspace() {
  const value = useContext(Ctx);
  if (!value) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  return value;
}

const messageOf = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [editor, setEditor] = useState<Workspace["editor"]>({ open: false, task: null });

  const reload = useCallback(async () => {
    setLoadError(null);
    try {
      // /me first: it provisions the profile and default categories on first sign-in.
      const profile = await api.me();
      const [cats, list, projs] = await Promise.all([
        api.categories.list(),
        api.tasks.list({ status: [...TASK_STATUSES] }),
        api.projects.list(),
      ]);
      setMe(profile);
      setCategories(cats);
      setTasks(list);
      setProjects(projs);
    } catch (e) {
      setLoadError(messageOf(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load on mount
    void reload();
  }, [reload]);

  const addTask = useCallback(async (input: TaskInput) => {
    try {
      const created = await api.tasks.create(input);
      setTasks((prev) => [created, ...prev]);
      return created;
    } catch (e) {
      toast.error(messageOf(e));
      return null;
    }
  }, []);

  const updateTask = useCallback(
    async (id: string, patch: TaskPatch) => {
      const previous = tasks.find((t) => t.id === id);
      setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
      try {
        const saved = await api.tasks.update(id, patch);
        setTasks((prev) => prev.map((t) => (t.id === id ? saved : t)));
        return true;
      } catch (e) {
        if (previous) setTasks((prev) => prev.map((t) => (t.id === id ? previous : t)));
        toast.error(messageOf(e));
        return false;
      }
    },
    [tasks],
  );

  const deleteTask = useCallback(
    async (id: string) => {
      const previous = tasks;
      setTasks((prev) => prev.filter((t) => t.id !== id));
      try {
        await api.tasks.remove(id);
        toast.success("Task deleted");
      } catch (e) {
        setTasks(previous);
        toast.error(messageOf(e));
      }
    },
    [tasks],
  );

  const toggleComplete = useCallback(
    async (task: Task) => {
      const done = task.status === "completed";
      await updateTask(task.id, { status: done ? "not_started" : "completed" });
    },
    [updateTask],
  );

  const createCategory = useCallback(async (name: string, color?: string) => {
    try {
      const created = await api.categories.create({ name, color });
      setCategories((prev) => [...prev, created]);
      return created;
    } catch (e) {
      toast.error(messageOf(e));
      return null;
    }
  }, []);

  // Priorities depend on the whole set (dependencies, the clock), so re-read rather than patch locally.
  const refreshTasks = useCallback(async () => {
    try {
      setTasks(await api.tasks.list({ status: [...TASK_STATUSES] }));
    } catch (e) {
      toast.error(messageOf(e));
    }
  }, []);

  const refreshProjects = useCallback(async () => {
    try {
      setProjects(await api.projects.list());
    } catch (e) {
      toast.error(messageOf(e));
    }
  }, []);

  const openEditor = useCallback(
    (task: Task | null = null, preset?: Partial<TaskInput>) => setEditor({ open: true, task, preset }),
    [],
  );
  const closeEditor = useCallback(() => setEditor((e) => ({ ...e, open: false })), []);

  const value = useMemo<Workspace>(
    () => ({
      me,
      tasks,
      categories,
      loading,
      loadError,
      reload,
      addTask,
      updateTask,
      deleteTask,
      toggleComplete,
      createCategory,
      projects,
      refreshProjects,
      refreshTasks,
      editor,
      openEditor,
      closeEditor,
    }),
    [me, tasks, categories, projects, loading, loadError, reload, addTask, updateTask, deleteTask, toggleComplete, createCategory, refreshProjects, refreshTasks, editor, openEditor, closeEditor],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
