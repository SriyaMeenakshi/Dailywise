import { Logo } from "@/components/logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col items-center px-4 py-8">
      <Logo />
      <main className="my-auto w-full max-w-sm py-10">
        <div className="rounded-2xl border bg-card p-6 shadow-raised sm:p-8">{children}</div>
      </main>
    </div>
  );
}
