"use client";
import { useEffect, useRef, useState } from "react";
import { api, useApi } from "@/lib/client/api";
import { Icon } from "./Icon";
import { Sheet } from "./ui";

type Msg = { role: "user" | "assistant"; content: string };
const SUGGESTIONS = ["How can I improve my rating?", "Why is my rating what it is?", "What does debt / EBITDA mean?"];

/** The company's coach. Answers only from the company's own verified figures; the service rejects replies with invented numbers. */
export function Assistant() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const assess = useApi<{ id: string }[]>("intelligence", open ? "/v1/assessments" : null);
  const end = useRef<HTMLDivElement>(null);
  const assessmentId = assess.data?.[0]?.id;
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy]);

  async function send(q: string) {
    const content = q.trim();
    if (!content || busy || !assessmentId) return;
    const next: Msg[] = [...msgs, { role: "user", content }];
    setMsgs(next); setText(""); setBusy(true); setErr("");
    try {
      const r = await api("advisory", "/v1/assistant/chat", { method: "POST", body: { assessment_id: assessmentId, messages: next.slice(-10) } });
      setMsgs([...next, { role: "assistant", content: r.reply }]);
    } catch (e: any) { setErr(e.detail ?? "The assistant is not available right now."); }
    finally { setBusy(false); }
  }

  return (
    <>
      <button className="fab" onClick={() => setOpen(true)} aria-label="Ask the assistant"><span className="tile sm c-blue"><Icon name="spark" /></span>Assistant</button>
      <Sheet open={open} onClose={() => setOpen(false)} title="Your assistant">
        <div className="stack">
          <p className="t-foot">Ask how to strengthen your profile. I only use your own figures and cannot promise a loan or a rate.</p>
          {!assessmentId && !assess.loading && <div className="banner info">Connect your accounting first, then I can look at your numbers.</div>}
          <div className="chat-log" aria-live="polite">
            {msgs.length === 0 && <div className="hstack wrap">{SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => send(s)} disabled={!assessmentId}>{s}</button>)}</div>}
            {msgs.map((m, i) => <div key={i} className={`bubble ${m.role === "user" ? "me" : "bot"}`}>{m.content}</div>)}
            {busy && <div className="bubble bot"><span className="typing" aria-label="Thinking"><i /><i /><i /></span></div>}
            <div ref={end} />
          </div>
          {err && <div className="banner" role="alert">{err}</div>}
          <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(text); }}>
            <input className="in" value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask a question" maxLength={600} aria-label="Your question" disabled={!assessmentId} />
            <button className="btn" type="submit" disabled={busy || !text.trim() || !assessmentId}>Send</button>
          </form>
          <p className="t-cap">AI-generated, preliminary and not financial advice.</p>
        </div>
      </Sheet>
    </>
  );
}
