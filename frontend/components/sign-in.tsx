"use client";

import { useState } from "react";
import Image from "next/image";
import { supabaseOrNull } from "@/lib/supabase";
import { SignInBackdrop } from "@/components/sign-in-backdrop";

type Provider = "google" | "github";
type Mode = "signin" | "signup";

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
    "inline-flex h-10 items-center justify-center gap-2.5 rounded-full border border-black/15 text-sm font-medium transition-colors hover:bg-black/5 disabled:opacity-50 dark:border-white/20 dark:hover:bg-white/10";
  const inputClass =
    "h-10 rounded-full border border-black/15 bg-transparent px-4 text-sm outline-none transition-colors placeholder:opacity-40 focus:border-black/40 dark:border-white/20 dark:focus:border-white/50";

  return (
    <main className="min-h-dvh lg:grid lg:grid-cols-2">
      {/* LEFT: brand hero + USP. The --brand panel stays dark in both themes. */}
      <section className="relative isolate flex flex-col overflow-hidden bg-brand px-8 py-12 text-brand-foreground lg:min-h-dvh lg:px-14 lg:py-16">
        <SignInBackdrop />

        <div className="rise relative z-10 flex items-center gap-2.5">
          <Mark />
          <span className="text-sm font-semibold tracking-tight">CiteMeRight</span>
        </div>

        <div className="relative z-10 mt-16 max-w-xl lg:my-auto">
          <h1
            className="rise text-[1.9rem] font-semibold leading-[1.12] tracking-tight sm:text-4xl lg:text-[2.7rem]"
            style={{ animationDelay: "70ms" }}
          >
            Reads the <span className="text-accent">citation graph</span> to tell you not just
            whether a precedent <span className="text-good">holds</span>, but{" "}
            <span className="whitespace-nowrap text-caution">how far</span>, and{" "}
            <span className="text-accent">why</span>.
          </h1>
          <p
            className="rise mt-6 text-base leading-relaxed text-brand-foreground/65 sm:text-lg"
            style={{ animationDelay: "140ms" }}
          >
            All grounded in the opinions that treat it.{" "}
            <span className="font-medium text-brand-foreground">Never a guess.</span>
          </p>
        </div>
      </section>

      {/* RIGHT: sign in / create account. */}
      <section className="flex items-center justify-center px-5 py-12 lg:min-h-dvh">
        <div
          className="rise w-full max-w-md rounded-3xl border border-black/10 bg-background/70 p-6 backdrop-blur-sm dark:border-white/15"
          style={{ animationDelay: "120ms" }}
        >
          <h2 className="text-base font-semibold">
            {mode === "signin" ? "Sign in" : "Create your account"}
          </h2>
          <p className="mt-1 text-sm opacity-60">
            {mode === "signin"
              ? "Pick up where you left off."
              : "Start checking precedent in seconds."}
          </p>

          <div className="mt-5 grid gap-2.5">
            <button type="button" onClick={() => onOAuth("google")} disabled={busy !== null} className={oauthClass}>
              <GoogleIcon />
              {busy === "google" ? "Redirecting…" : "Continue with Google"}
            </button>
            <button type="button" onClick={() => onOAuth("github")} disabled={busy !== null} className={oauthClass}>
              <GitHubIcon />
              {busy === "github" ? "Redirecting…" : "Continue with GitHub"}
            </button>
          </div>

          <div className="my-5 flex items-center gap-3">
            <div className="h-px flex-1 bg-black/10 dark:bg-white/15" />
            <span className="text-[11px] uppercase tracking-widest opacity-40">or with email</span>
            <div className="h-px flex-1 bg-black/10 dark:bg-white/15" />
          </div>

          <form onSubmit={onEmail} className="grid gap-2.5">
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
              className="mt-1 h-10 rounded-full bg-foreground text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {busy === "email"
                ? "Working…"
                : mode === "signin"
                  ? "Sign in"
                  : "Create account"}
            </button>
          </form>

          <p className="mt-5 text-center text-sm opacity-60">
            {mode === "signin" ? "No account yet?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "signin" ? "signup" : "signin");
                setError(null);
                setNotice(null);
              }}
              className="font-medium underline underline-offset-2 hover:opacity-80"
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
    <Image
      src="/logo.png"
      alt="CiteMeRight"
      width={28}
      height={28}
      priority
      className="h-7 w-7 rounded-[9px] shadow-sm ring-1 ring-black/10 dark:ring-white/15"
    />
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
