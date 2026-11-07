"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Catches unexpected rendering errors inside the signed-in app, so one bad page never blanks the shell. */
export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div role="alert" className="mx-auto flex max-w-md flex-col items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center">
      <AlertTriangle className="size-6 text-destructive" aria-hidden />
      <h1 className="text-title">That didn’t work</h1>
      <p className="text-sm text-muted-foreground">Something went wrong showing this page. Your data is safe. Try again, and if it keeps happening, reload the app.</p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
