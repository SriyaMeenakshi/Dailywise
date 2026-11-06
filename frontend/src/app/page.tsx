import Link from "next/link";
import { ArrowRight, CalendarClock, Layers, Zap } from "lucide-react";
import { Logo } from "@/components/logo";
import { buttonVariants } from "@/components/ui/button";

const POINTS = [
  { icon: Zap, title: "Capture in seconds", body: "One line, one Enter. Details like deadlines, estimates and energy can wait until you need them." },
  { icon: Layers, title: "Sorted your way", body: "Your own categories, statuses and filters keep coursework, projects and life from blurring together." },
  { icon: CalendarClock, title: "See the day clearly", body: "A calm Today view puts what’s overdue, due and important in front of you, and nothing else." },
];

const SAMPLE = [
  { title: "DBMS assignment", meta: "Academic · Friday", tone: "clay" },
  { title: "Read NLP chapters 3–4", meta: "Learning · 90m", tone: "sage" },
  { title: "Finish project API endpoints", meta: "Projects · This week", tone: "amber" },
] as const;

const DOT = { clay: "bg-clay", sage: "bg-sage", amber: "bg-amber" } as const;

export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
        <Logo />
        <nav aria-label="Account" className="flex items-center gap-2">
          <Link href="/login" className={buttonVariants({ variant: "ghost" })}>
            Sign in
          </Link>
          <Link href="/signup" className={buttonVariants()}>
            Get started
          </Link>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 sm:px-8">
        <section className="grid items-center gap-12 py-12 md:grid-cols-[1.15fr_1fr] md:py-24">
          <div>
            <p className="text-section">For students who carry a lot</p>
            <h1 className="text-display mt-4 max-w-xl text-balance">
              Your day. Your priorities. <em className="text-clay not-italic">Your progress.</em>
            </h1>
            <p className="mt-6 max-w-md text-lg leading-relaxed text-muted-foreground">
              Daywise is a quiet place to put everything you need to do, and to see what deserves your attention today.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className={buttonVariants({ size: "lg", className: "h-11 px-5 text-[15px]" })}>
                Start planning <ArrowRight />
              </Link>
              <Link href="/login" className={buttonVariants({ variant: "outline", size: "lg", className: "h-11 px-5 text-[15px]" })}>
                I have an account
              </Link>
            </div>
          </div>

          <figure aria-label="Example of a Daywise task list" className="rounded-2xl border bg-card p-5 shadow-raised">
            <figcaption className="text-section">An example morning</figcaption>
            <ul className="mt-4 space-y-2.5">
              {SAMPLE.map((s) => (
                <li key={s.title} className="flex items-start gap-3 rounded-xl border bg-background px-3.5 py-3">
                  <span aria-hidden className="mt-0.5 size-[18px] shrink-0 rounded-full border border-input" />
                  <span>
                    <span className="block text-[15px] font-medium">{s.title}</span>
                    <span className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span aria-hidden className={`size-2 rounded-full ${DOT[s.tone]}`} />
                      {s.meta}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </figure>
        </section>

        <section aria-label="What Daywise does" className="grid gap-8 border-t py-14 md:grid-cols-3">
          {POINTS.map((p) => (
            <div key={p.title}>
              <p.icon className="size-5 text-clay" aria-hidden />
              <h2 className="mt-4 text-xl">{p.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{p.body}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="mx-auto w-full max-w-6xl px-5 py-8 text-sm text-muted-foreground sm:px-8">
        Daywise · Your day. Your priorities. Your progress.
      </footer>
    </div>
  );
}
