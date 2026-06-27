"use client";

// Shared citator chat. Two mount points, one component:
//   - global (no caseId)  — doctrinal questions across the source graph.
//   - case-scoped (caseId) — the analysis page; answers about the case on screen.
// POSTs to /chat (public, multi-turn, agentic + graph-grounded — see
// app/src/htl/routes/chat.py). Styled to the citator's slate surface, sky accent.
import { useEffect, useRef, useState } from "react";
import { chat, type ChatTurn } from "@/lib/api";

// ponytail: tiny markdown for the model's output subset (bold / italic / bullets /
// paragraphs). Swap for react-markdown if replies ever need tables, links, code.
function inline(text: string, k: string): React.ReactNode[] {
  return text.split(/(\*\*\*.+?\*\*\*|\*\*.+?\*\*|\*.+?\*)/g).map((p, i) => {
    const key = `${k}-${i}`;
    if (/^\*\*\*.+\*\*\*$/.test(p)) return <strong key={key}><em>{p.slice(3, -3)}</em></strong>;
    if (/^\*\*.+\*\*$/.test(p)) return <strong key={key}>{p.slice(2, -2)}</strong>;
    if (/^\*.+\*$/.test(p)) return <em key={key}>{p.slice(1, -1)}</em>;
    return <span key={key}>{p}</span>;
  });
}

function Markdown({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (!bullets.length) return;
    const at = blocks.length;
    blocks.push(
      <ul key={`ul-${at}`} className="list-disc space-y-1 pl-4">
        {bullets.map((b, i) => <li key={i}>{inline(b, `li-${at}-${i}`)}</li>)}
      </ul>,
    );
    bullets = [];
  };
  for (const line of text.split("\n")) {
    const m = line.match(/^\s*[*-]\s+(.*)$/);
    if (m) { bullets.push(m[1]); continue; }
    flush();
    if (line.trim()) blocks.push(<p key={`p-${blocks.length}`}>{inline(line, `p-${blocks.length}`)}</p>);
  }
  flush();
  return <div className="space-y-2">{blocks}</div>;
}

export function Chat({
  caseId,
  starters = [],
  placeholder = "Ask about a case or the doctrine…",
}: {
  caseId?: number;
  starters?: string[];
  placeholder?: string;
}) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // Scoped chat is about a different case each time caseId changes → start fresh.
  useEffect(() => {
    setTurns([]);
    setError(null);
  }, [caseId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, loading]);

  async function send(message: string) {
    const m = message.trim();
    if (!m || loading) return;
    setInput("");
    setError(null);
    const history = turns; // the turns BEFORE this message
    setTurns([...history, { role: "user", content: m }]);
    setLoading(true);
    try {
      const reply = await chat(m, history, caseId);
      setTurns((t) => [...t, { role: "assistant", content: reply }]);
    } catch {
      setError("Couldn't reach the assistant — is the API up?");
    } finally {
      setLoading(false);
    }
  }

  const empty = turns.length === 0;

  return (
    <div className="flex flex-col">
      {/* Transcript */}
      {!empty && (
        <div className="max-h-[420px] space-y-4 overflow-y-auto pr-1">
          {turns.map((t, i) =>
            t.role === "user" ? (
              <div key={i} className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-sky-500 px-4 py-2 text-sm font-medium text-white">
                  {t.content}
                </p>
              </div>
            ) : (
              <div key={i} className="flex justify-start">
                <div className="max-w-[92%] rounded-2xl rounded-bl-sm border border-white/10 bg-white/5 px-4 py-2.5 text-sm leading-relaxed text-slate-200">
                  <Markdown text={t.content} />
                </div>
              </div>
            ),
          )}
          {loading && (
            <div className="flex justify-start">
              <p className="rounded-2xl rounded-bl-sm border border-white/10 bg-white/5 px-4 py-3">
                <span className="inline-flex gap-1">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" />
                </span>
              </p>
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}

      {/* Starter prompts (empty state) */}
      {empty && starters.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {starters.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => send(s)}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-left text-xs text-slate-300 transition hover:border-sky-400/50 hover:text-white"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

      {/* Composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className={`flex gap-2 ${empty ? "" : "mt-4"}`}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder}
          className="flex-1 rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-400/50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-full bg-sky-500 px-5 text-sm font-medium text-white transition hover:bg-sky-400 disabled:opacity-40"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
