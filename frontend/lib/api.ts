const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export type Turn = { role: "user" | "assistant"; content: string };

export async function sendChat(message: string, history: Turn[]): Promise<string> {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = (await res.json()) as { reply: string };
  return data.reply;
}
