"use client";

import { useState } from "react";
import { supabaseOrNull } from "@/lib/supabase";

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

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-center px-6 py-10">
      <div className="rounded-3xl border border-black/10 p-7 dark:border-white/15">
        <h1 className="text-lg font-semibold">Hack the Law — Legal Assistant</h1>
        <p className="mt-1 text-sm opacity-60">Sign in to start chatting.</p>

        <div className="mt-6 grid gap-2">
          <button
            type="button"
            onClick={() => onOAuth("google")}
            disabled={busy !== null}
            className="inline-flex h-11 items-center justify-center gap-2.5 rounded-full border border-black/15 text-sm font-medium transition-colors hover:bg-black/5 disabled:opacity-50 dark:border-white/20 dark:hover:bg-white/10"
          >
            <GoogleIcon />
            {busy === "google" ? "Redirecting…" : "Continue with Google"}
          </button>
          <button
            type="button"
            onClick={() => onOAuth("github")}
            disabled={busy !== null}
            className="inline-flex h-11 items-center justify-center gap-2.5 rounded-full border border-black/15 text-sm font-medium transition-colors hover:bg-black/5 disabled:opacity-50 dark:border-white/20 dark:hover:bg-white/10"
          >
            <GitHubIcon />
            {busy === "github" ? "Redirecting…" : "Continue with GitHub"}
          </button>
        </div>

        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-black/10 dark:bg-white/15" />
          <span className="text-[11px] uppercase tracking-widest opacity-50">or</span>
          <div className="h-px flex-1 bg-black/10 dark:bg-white/15" />
        </div>

        <form onSubmit={onEmail} className="grid gap-3">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            className="h-11 rounded-xl border border-black/15 bg-transparent px-3.5 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
          />
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            className="h-11 rounded-xl border border-black/15 bg-transparent px-3.5 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
          />

          {error && (
            <p className="text-sm text-red-500" role="alert">
              {error}
            </p>
          )}
          {notice && <p className="text-sm text-green-600 dark:text-green-400">{notice}</p>}

          <button
            type="submit"
            disabled={busy !== null}
            className="h-11 rounded-full bg-foreground text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy === "email"
              ? "Working…"
              : mode === "signin"
                ? "Sign in"
                : "Create account"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm opacity-70">
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
    </main>
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
