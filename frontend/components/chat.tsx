"use client";

import { useState } from "react";
import { sendChat, type Turn } from "@/lib/api";
import { AccountMenu } from "@/components/account-menu";

export function Chat({ email }: { email: string }) {
  const [messages, setMessages] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const history = messages;
    setMessages([...history, { role: "user", content: text }]);
    setInput("");
    setError(null);
    setLoading(true);
    try {
      const reply = await sendChat(text, history);
      setMessages((m) => [...m, { role: "assistant", content: reply }]);
    } catch {
      setError("Something went wrong — is the API running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex h-dvh w-full max-w-2xl flex-col px-4">
      <header className="flex items-center justify-between gap-3 py-5">
        <div>
          <h1 className="text-lg font-semibold">Hack the Law — Legal Assistant</h1>
          <p className="text-xs opacity-60">General information, not legal advice.</p>
        </div>
        <AccountMenu email={email} />
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto pb-4">
        {messages.length === 0 && (
          <p className="mt-10 text-center text-sm opacity-50">
            Ask a legal question to get started.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
          >
            <div
              className={
                "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm " +
                (m.role === "user"
                  ? "bg-foreground text-background"
                  : "bg-black/5 dark:bg-white/10")
              }
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && <p className="text-sm opacity-50">Thinking…</p>}
        {error && <p className="text-sm text-red-500">{error}</p>}
      </div>

      <form onSubmit={onSubmit} className="flex gap-2 py-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question…"
          className="flex-1 rounded-full border border-black/15 bg-transparent px-4 py-2 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </main>
  );
}
