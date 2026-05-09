import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { RefreshCw, Send, Sparkles } from "lucide-react";
import { api } from "@/lib/api";

// ── Suggested prompts (mockup parity) ────────────────────────────────────────
const SUGGESTIONS = [
  "what should I cut to save $200/mo?",
  "savings rate vs last month",
  "any unusual spending lately?",
  "am I on track for my goals?",
];

type Turn = { role: "user" | "ai"; text: string };

export default function Ask() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);
  const tailRef = useRef<HTMLDivElement>(null);

  const askMut = useMutation({
    mutationFn: (q: string) => api.ask(q),
    onMutate: (q) => {
      setTurns((t) => [...t, { role: "user", text: q }]);
    },
    onSuccess: (res) => {
      setTurns((t) => [...t, { role: "ai", text: res.answer }]);
    },
    onError: (err: Error) => {
      setTurns((t) => [...t, { role: "ai", text: `(error: ${err.message ?? "request failed"})` }]);
    },
  });

  const submit = () => {
    const q = draft.trim();
    if (!q || askMut.isPending) return;
    setDraft("");
    askMut.mutate(q);
  };

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [draft]);

  // Scroll to newest turn
  useEffect(() => {
    tailRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, askMut.isPending]);

  const reset = () => {
    setTurns([]);
    setDraft("");
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Top bar ─────────────────────────────────────────────────────────── */}
      <div className="px-5 pt-4 pb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-sm" style={{ background: "#0a0a0a" }} />
          <span className="text-[13px] font-semibold tracking-tight">Ask</span>
          <span className="num text-[10px] px-1.5 py-0.5 rounded border border-[#e5e5e5] bg-[#f4f4f5] text-[#525252] flex items-center gap-1">
            <Sparkles size={10} strokeWidth={1.75} />
            advisor
          </span>
        </div>
        <button
          onClick={reset}
          className="text-neutral-500 text-[11px] flex items-center gap-1"
          aria-label="New conversation"
        >
          <RefreshCw size={12} strokeWidth={1.75} />
          new
        </button>
      </div>

      <div className="hr" />

      {/* ── Conversation ────────────────────────────────────────────────────── */}
      <div className="flex-1 px-4 py-4 space-y-4 pb-[148px]">
        {turns.length === 0 && (
          <div className="text-center text-[12px] text-neutral-400 py-12">
            Ask anything. Examples below.
          </div>
        )}

        {turns.map((t, i) =>
          t.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div
                className="max-w-[80%] px-3 py-2 text-[12.5px] whitespace-pre-wrap"
                style={{
                  background: "#0a0a0a",
                  color: "#fafafa",
                  borderRadius: "14px 14px 4px 14px",
                }}
              >
                {t.text}
              </div>
            </div>
          ) : (
            <div key={i} className="flex">
              <div
                className="max-w-[88%] px-3 py-2.5 text-[12.5px] whitespace-pre-wrap leading-relaxed"
                style={{
                  background: "#f4f4f5",
                  color: "#0a0a0a",
                  border: "1px solid #e5e5e5",
                  borderRadius: "14px 14px 14px 4px",
                }}
              >
                {t.text}
              </div>
            </div>
          )
        )}

        {askMut.isPending && (
          <div className="flex">
            <div
              className="px-3 py-2 text-[12.5px] flex items-center gap-1.5"
              style={{
                background: "#f4f4f5",
                border: "1px solid #e5e5e5",
                borderRadius: "14px 14px 14px 4px",
              }}
            >
              <span className="dot" />
              <span className="dot" style={{ animationDelay: "0.15s" }} />
              <span className="dot" style={{ animationDelay: "0.3s" }} />
            </div>
          </div>
        )}

        <div ref={tailRef} />
      </div>

      {/* ── Suggested prompts + input (pinned above bottom nav) ─────────────── */}
      <div
        className="fixed bottom-14 inset-x-0 px-4 pb-2 pt-2 backdrop-blur border-t border-[#e5e5e5]"
        style={{ background: "rgba(250,250,250,0.95)" }}
      >
        <div className="max-w-2xl mx-auto">
          <div
            className="flex gap-1.5 overflow-x-auto mb-2 -mx-1 px-1"
            style={{ scrollbarWidth: "none" }}
          >
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => {
                  setDraft(s);
                  taRef.current?.focus();
                }}
                className="shrink-0 px-2.5 py-1 rounded-full border border-[#e5e5e5] bg-white text-[11px] text-neutral-600 hover:bg-neutral-50"
              >
                {s}
              </button>
            ))}
          </div>
          <div className="flex items-end gap-2 px-3 py-2 rounded-md border border-[#e5e5e5] bg-white">
            <textarea
              ref={taRef}
              rows={1}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKey}
              placeholder="Ask anything about your finances…"
              className="bg-transparent flex-1 text-[12.5px] outline-none resize-none placeholder:text-neutral-400 leading-snug"
              disabled={askMut.isPending}
            />
            <button
              onClick={submit}
              disabled={!draft.trim() || askMut.isPending}
              className="w-7 h-7 grid place-items-center rounded-md disabled:opacity-30"
              style={{ background: "#0a0a0a", color: "#fafafa" }}
              aria-label="Send"
            >
              <Send size={14} strokeWidth={1.75} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
