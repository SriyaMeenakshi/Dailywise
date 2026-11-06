import Link from "next/link";
import { cn } from "cn";

export function Logo({ className, href = "/" }: { className?: string; href?: string }) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-2 rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50", className)}>
      <span aria-hidden className="relative size-6 rounded-full bg-primary">
        <span className="absolute top-1/2 left-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-clay" />
      </span>
      <span className="font-display text-xl tracking-tight">Daywise</span>
    </Link>
  );
}
