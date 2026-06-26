"use client";

import { useAuth } from "@/lib/auth";
import { SignIn } from "@/components/sign-in";
import { Chat } from "@/components/chat";

export default function Home() {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <main className="flex min-h-dvh items-center justify-center">
        <p className="text-sm opacity-50">Loading…</p>
      </main>
    );
  }

  if (!session) return <SignIn />;

  return <Chat email={session.user.email ?? "Account"} />;
}
