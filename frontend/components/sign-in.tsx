"use client";

import { useState } from "react";
import { supabaseOrNull } from "@/lib/supabase";

type Provider = "google" | "github";
type Mode = "signin" | "signup";

// Live product demo for the brand panel: real verdict states (good law /
// eroding / overruled) — the actual output of the citator, not stock imagery.
const TONE = {
  good: { dot: "bg-good ring-good/15", pill: "bg-good/15 text-good" },
  caution: { dot: "bg-caution ring-caution/15", pill: "bg-caution/15 text-caution" },
  risk: { dot: "bg-risk ring-risk/15", pill: "bg-risk/15 text-risk" },
} as const;

const VERDICTS: { case: string; cite: string; state: string; tone: keyof typeof TONE }[] = [
  { case: "Roe v. Wade", cite: "410 U.S. 113", state: "Overruled", tone: "risk" },
  { case: "Auer v. Robbins", cite: "519 U.S. 452", state: "Narrowed", tone: "caution" },
  { case: "NYSRPA v. Bruen", cite: "597 U.S. 1", state: "Good law", tone: "good" },
];

export function SignIn() {
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<null | "email" | Provider>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function onOAuth(provider: Provider) {
    setError(null);
    const sb = supabaseOrNull();
    if (!sb) {
      setError("Sign-in isn't configured in this environment.");
      return;
    }
    setBusy(provider);
    const { error } = await sb.auth.signInWithOAuth({
      provider,
      options: { redirectTo: window.location.origin },
    });
    // On success the browser redirects away; only reached on error.
    if (error) {
      setError(error.message);
      setBusy(null);
    }
  }

  async function onEmail(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    const sb = supabaseOrNull();
    if (!sb) {
      setError("Sign-in isn't configured in this environment.");
      return;
    }
    setBusy("email");
    const creds = { email: email.trim(), password };
    const { data, error } =
      mode === "signin"
        ? await sb.auth.signInWithPassword(creds)
        : await sb.auth.signUp(creds);
    setBusy(null);
    if (error) {
      setError(error.message);
      return;
    }
    // Sign-up with email confirmation ON returns a user but no session.
    if (mode === "signup" && !data.session) {
      setNotice("Check your email to confirm your account, then sign in.");
      setMode("signin");
    }
    // Otherwise onAuthStateChange flips the app into its authed state.
  }

  const oauthClass =
    "inline-flex h-11 items-center justify-center gap-2.5 rounded-xl border border-border text-sm font-medium transition-colors hover:bg-foreground/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50";
  const inputClass =
    "h-11 rounded-xl border border-border bg-surface px-3.5 text-sm outline-none transition-colors placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-ring/25";

  return (
    <main className="min-h-dvh w-full min-w-0 lg:grid lg:grid-cols-[1.05fr_1fr]">
      {/* ── Brand panel — always dark, carries the identity ───────────────── */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-brand px-10 py-12 text-brand-foreground lg:flex xl:px-14">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-28 -top-28 h-96 w-96 rounded-full bg-accent/20 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-36 -left-24 h-80 w-80 rounded-full bg-accent/10 blur-3xl"
        />

        <div className="rise relative flex items-center gap-2.5">
          <Mark />
          <span className="text-sm font-semibold tracking-tight">Hack the Law</span>
        </div>

        <div className="relative max-w-xl">
          <h1
            className="rise text-balance text-[clamp(2.4rem,4.6vw,3.6rem)] font-semibold leading-[1.04] tracking-[-0.03em]"
            style={{ animationDelay: "60ms" }}
          >
            Is it still good law?
          </h1>
          <p
            className="rise mt-5 max-w-md text-[15px] leading-relaxed text-brand-foreground/70"
            style={{ animationDelay: "130ms" }}
          >
            An AI assistant that reads the citation graph and tells you whether a case
            still holds — before you stake an argument on it.
          </p>

          <div className="rise mt-9 space-y-2" style={{ animationDelay: "210ms" }}>
            {VERDICTS.map((v) => (
              <div
                key={v.case}
                className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 backdrop-blur-sm"
              >
                <span className={`h-2.5 w-2.5 shrink-0 rounded-full ring-4 ${TONE[v.tone].dot}`} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{v.case}</p>
                  <p className="truncate text-[11px] text-brand-foreground/50">{v.cite}</p>
                </div>
                <span
                  className={`ml-auto shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${TONE[v.tone].pill}`}
                >
                  {v.state}
                </span>
              </div>
            ))}
          </div>
        </div>

        <p className="rise relative text-xs text-brand-foreground/40" style={{ animationDelay: "300ms" }}>
          General information, not legal advice.
        </p>
      </section>

      {/* ── Auth panel ────────────────────────────────────────────────────── */}
      <section className="flex min-h-dvh items-center justify-center px-6 py-12 sm:px-10 lg:min-h-0">
        <div className="rise w-full max-w-sm" style={{ animationDelay: "120ms" }}>
          <div className="mb-9 flex items-center gap-2.5 lg:hidden">
            <Mark />
            <span className="text-sm font-semibold tracking-tight">Hack the Law</span>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight">
            {mode === "signin" ? "Welcome back" : "Create your account"}
          </h2>
          <p className="mt-1.5 text-sm text-muted">
            {mode === "signin"
              ? "Sign in to pick up where you left off."
              : "Start checking precedent in seconds."}
          </p>

          <div className="mt-7 grid gap-2.5">
            <button type="button" onClick={() => onOAuth("google")} disabled={busy !== null} className={oauthClass}>
              <GoogleIcon />
              {busy === "google" ? "Redirecting…" : "Continue with Google"}
            </button>
            <button type="button" onClick={() => onOAuth("github")} disabled={busy !== null} className={oauthClass}>
              <GitHubIcon />
              {busy === "github" ? "Redirecting…" : "Continue with GitHub"}
            </button>
          </div>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-[11px] uppercase tracking-widest text-muted">or with email</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={onEmail} className="grid gap-3">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              className={inputClass}
            />
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              className={inputClass}
            />

            {error && (
              <p className="text-sm text-red-600 dark:text-red-400" role="alert">
                {error}
              </p>
            )}
            {notice && <p className="text-sm text-green-700 dark:text-green-400">{notice}</p>}

            <button
              type="submit"
              disabled={busy !== null}
              className="mt-1 h-11 rounded-xl bg-primary text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50"
            >
              {busy === "email"
                ? "Working…"
                : mode === "signin"
                  ? "Sign in"
                  : "Create account"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            {mode === "signin" ? "No account yet?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "signin" ? "signup" : "signin");
                setError(null);
                setNotice(null);
              }}
              className="font-medium text-primary underline-offset-2 hover:underline"
            >
              {mode === "signin" ? "Create one" : "Sign in"}
            </button>
          </p>
        </div>
      </section>
    </main>
  );
}

function Mark() {
  return (
    <span className="grid h-7 w-7 place-items-center rounded-[9px] bg-primary text-primary-foreground shadow-sm">
      <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden>
        <path d="M3 8.5l3 3 7-7.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden>
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.02-3.7H.96v2.34A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.98 10.72a5.4 5.4 0 0 1 0-3.44V4.94H.96a9 9 0 0 0 0 8.12l3.02-2.34Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 .96 4.94l3.02 2.34C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.4 7.4 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}
