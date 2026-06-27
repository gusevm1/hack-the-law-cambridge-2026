"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { SignIn } from "@/components/sign-in";

export default function Home() {
  const { session, loading } = useAuth();
  const router = useRouter();

  // Signed in → the citator is the product. Send them there.
  useEffect(() => {
    if (!loading && session) router.replace("/citator");
  }, [loading, session, router]);

  if (loading || session) {
    return (
      <main className="flex min-h-dvh items-center justify-center">
        <p className="text-sm opacity-50">Loading…</p>
      </main>
    );
  }

  return <SignIn />;
}
