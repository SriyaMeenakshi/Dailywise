"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getSupabase, isSupabaseConfigured } from "@/lib/supabase/client";

const loginSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});
const signupSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(8, "Use at least 8 characters").max(72, "Use at most 72 characters"),
});
type Values = z.infer<typeof loginSchema>;

function safeNext(next: string | null) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

function Form({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmEmail, setConfirmEmail] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(mode === "login" ? loginSchema : signupSchema) });

  async function onSubmit({ email, password }: Values) {
    setFormError(null);
    try {
      const auth = getSupabase().auth;
      if (mode === "login") {
        const { error } = await auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { data, error } = await auth.signUp({ email, password });
        if (error) throw error;
        if (!data.session) {
          setConfirmEmail(email);
          return;
        }
      }
      router.replace(next);
      router.refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      setFormError(
        /invalid login/i.test(msg)
          ? "That email and password don’t match."
          : msg || "Something went wrong. Please try again.",
      );
    }
  }

  if (confirmEmail) {
    return (
      <div className="space-y-3 text-center">
        <MailCheck className="mx-auto size-8 text-sage" aria-hidden />
        <h1 className="text-title">Check your inbox</h1>
        <p className="text-sm text-muted-foreground">
          We sent a confirmation link to <span className="font-medium text-foreground">{confirmEmail}</span>. Open it, then sign in.
        </p>
        <Link href="/login" className="inline-block text-sm font-medium underline underline-offset-4">
          Go to sign in
        </Link>
      </div>
    );
  }

  const login = mode === "login";
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
      <div className="space-y-1">
        <h1 className="text-title">{login ? "Welcome back" : "Create your Daywise"}</h1>
        <p className="text-sm text-muted-foreground">{login ? "Pick up where you left off." : "Free while we build it. No card needed."}</p>
      </div>

      {!isSupabaseConfigured && (
        <p role="alert" className="rounded-lg border border-amber/40 bg-amber-soft px-3 py-2 text-sm">
          Supabase isn’t configured. Add the values from <code>frontend/.env.example</code> to <code>.env.local</code> and restart the dev server.
        </p>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" autoComplete="email" autoFocus aria-invalid={!!errors.email} {...register("email")} />
        {errors.email && <p role="alert" className="text-xs text-destructive">{errors.email.message}</p>}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="password">Password</Label>
        <Input id="password" type="password" autoComplete={login ? "current-password" : "new-password"} aria-invalid={!!errors.password} {...register("password")} />
        {errors.password && <p role="alert" className="text-xs text-destructive">{errors.password.message}</p>}
      </div>

      {formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}

      <Button type="submit" className="h-10 w-full" disabled={isSubmitting || !isSupabaseConfigured}>
        {isSubmitting ? "One moment…" : login ? "Sign in" : "Create account"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        {login ? "New to Daywise? " : "Already have an account? "}
        <Link href={login ? "/signup" : "/login"} className="font-medium text-foreground underline underline-offset-4">
          {login ? "Create an account" : "Sign in"}
        </Link>
      </p>
    </form>
  );
}

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  return (
    <Suspense fallback={null}>
      <Form mode={mode} />
    </Suspense>
  );
}
