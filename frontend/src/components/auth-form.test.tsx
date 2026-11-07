import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthForm } from "@/components/auth-form";

const auth = { signInWithPassword: vi.fn(), signUp: vi.fn() };
const router = { replace: vi.fn(), refresh: vi.fn() };
let nextParam: string | null = null;

vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => ({ get: (k: string) => (k === "next" ? nextParam : null) }),
}));
vi.mock("@/lib/supabase/client", () => ({
  isSupabaseConfigured: true,
  getSupabase: () => ({ auth }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  nextParam = null;
});

async function fill(email: string, password: string) {
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
}

describe("sign in", () => {
  it("validates before calling the server", async () => {
    render(<AuthForm mode="login" />);
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(screen.getByText("Enter your password")).toBeInTheDocument();
    expect(auth.signInWithPassword).not.toHaveBeenCalled();
  });

  it("signs in and goes to the dashboard", async () => {
    auth.signInWithPassword.mockResolvedValue({ error: null });
    render(<AuthForm mode="login" />);
    await fill("a@b.co", "hunter22");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/dashboard"));
    expect(auth.signInWithPassword).toHaveBeenCalledWith({ email: "a@b.co", password: "hunter22" });
  });

  it("returns to the page you were sent from, but never to another site", async () => {
    auth.signInWithPassword.mockResolvedValue({ error: null });
    nextParam = "/planner";
    const { unmount } = render(<AuthForm mode="login" />);
    await fill("a@b.co", "pw");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/planner"));
    unmount();
    router.replace.mockClear();

    nextParam = "//evil.example.com";
    render(<AuthForm mode="login" />);
    await fill("a@b.co", "pw");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("shows a friendly message for wrong credentials", async () => {
    auth.signInWithPassword.mockResolvedValue({ error: new Error("Invalid login credentials") });
    render(<AuthForm mode="login" />);
    await fill("a@b.co", "nope");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That email and password don’t match.");
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("sign up", () => {
  it("requires a password of at least 8 characters", async () => {
    render(<AuthForm mode="signup" />);
    await fill("a@b.co", "short");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Use at least 8 characters")).toBeInTheDocument();
    expect(auth.signUp).not.toHaveBeenCalled();
  });

  it("asks you to confirm your email when no session is returned", async () => {
    auth.signUp.mockResolvedValue({ data: { session: null }, error: null });
    render(<AuthForm mode="signup" />);
    await fill("new@user.co", "longenough1");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Check your inbox")).toBeInTheDocument();
    expect(screen.getByText("new@user.co")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
  });
});
