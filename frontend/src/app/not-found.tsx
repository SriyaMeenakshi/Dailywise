import Link from "next/link";
import { Logo } from "@/components/logo";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <Logo />
      <h1 className="text-display mt-4">Lost your place?</h1>
      <p className="max-w-sm text-muted-foreground">We couldn’t find that page. It may have moved, or the link may be wrong.</p>
      <Link href="/dashboard" className={buttonVariants({ size: "lg", className: "mt-2" })}>
        Back to today
      </Link>
    </main>
  );
}
