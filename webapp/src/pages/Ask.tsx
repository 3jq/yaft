import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { api } from "@/lib/api";
import { Hr } from "@/components/Section";

// ── Suggested chips ───────────────────────────────────────────────────────────

const SUGGESTIONS = [
  "How much did I spend on food this month?",
  "What is my biggest expense category?",
  "Am I on track with my budget?",
  "How long will my savings last?",
];

// ── Main component ────────────────────────────────────────────────────────────

type QAPair = { q: string; a: string };

export default function Ask() {
  const nav = useNavigate();
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<QAPair[]>([]);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const askMut = useMutation({
    mutationFn: (q: string) => api.ask(q),
    onSuccess: (res, q) => {
      setHistory((h) => [{ q, a: res.answer }, ...h]);
      setQuestion("");
      setError(null);
    },
    onError: (err: Error) => {
      setError(err.message ?? "Something went wrong. Please try again.");
    },
  });

  const handleSubmit = () => {
    const q = question.trim();
    if (!q || askMut.isPending) return;
    setError(null);
    askMut.mutate(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [question]);

  return (
    <div className="pb-20">
      {/* ── Top bar ──────────────────────────────────────────────────────────── */}
      <div className="px-4 pt-4 pb-3 flex items-center justify-between">
        <button
          onClick={() => nav(-1)}
          className="w-8 h-8 flex items-center justify-center text-neutral-600 -ml-1"
          aria-label="Back"
        >
          <ChevronLeft size={20} strokeWidth={1.75} />
        </button>
        <span className="text-[13px] font-semibold tracking-tight">Ask</span>
        <div className="w-5" />
      </div>

      <Hr />

      {/* ── Input area ───────────────────────────────────────────────────────── */}
      <div className="px-5 py-4">
        {/* Suggestion chips */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => {
                setQuestion(s);
                textareaRef.current?.focus();
              }}
              className="inline-flex items-center px-2.5 py-1 rounded-full border border-border text-[11px] text-neutral-600 bg-white hover:bg-neutral-50"
            >
              {s}
            </button>
          ))}
        </div>

        {/* Textarea + Send */}
        <div className="border border-border rounded-md bg-white overflow-hidden">
          <textarea
            ref={textareaRef}
            rows={2}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your finances…"
            className="w-full px-3 py-2.5 text-[13px] bg-transparent outline-none resize-none leading-snug"
            style={{ minHeight: 56 }}
            disabled={askMut.isPending}
          />
          <div className="px-3 pb-2.5 flex items-center justify-between border-t border-[#f0f0f1]">
            <span className="num text-[10px] text-neutral-400">
              {askMut.isPending ? (
                <span className="flex items-center gap-1.5">
                  <span
                    className="inline-block w-1.5 h-1.5 rounded-full bg-foreground"
                    style={{ animation: "pulse 1.2s ease-in-out infinite" }}
                  />
                  Thinking…
                </span>
              ) : (
                "↵ enter to send"
              )}
            </span>
            <button
              onClick={handleSubmit}
              disabled={!question.trim() || askMut.isPending}
              className="inline-flex items-center px-3 py-1.5 rounded-md text-[12px] font-medium bg-foreground text-background disabled:opacity-30"
            >
              Ask
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mt-2 text-[11px] text-neutral-500 num border border-[#e5e5e5] rounded-md px-3 py-2 bg-white">
            {error}
          </div>
        )}
      </div>

      <Hr />

      {/* ── History ──────────────────────────────────────────────────────────── */}
      {history.length === 0 && !askMut.isPending && (
        <div className="px-5 py-6 text-center text-[12px] text-neutral-400">
          Your answers will appear here.
        </div>
      )}

      {history.map((pair, i) => (
        <div key={i}>
          <div className="px-5 py-4">
            {/* Question */}
            <div className="num text-[10.5px] text-neutral-400 mb-1 uppercase tracking-wide">Q</div>
            <div className="text-[13px] font-medium mb-3">{pair.q}</div>

            {/* Answer */}
            <div className="num text-[10.5px] text-neutral-400 mb-1 uppercase tracking-wide">A</div>
            <div className="text-[13px] text-neutral-700 whitespace-pre-wrap leading-relaxed">
              {pair.a}
            </div>
          </div>
          {i < history.length - 1 && <Hr />}
        </div>
      ))}
    </div>
  );
}
