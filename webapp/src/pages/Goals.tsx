import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Plus, Archive } from "lucide-react";
import { api } from "@/lib/api";
import { formatAmount, toMinor } from "@/lib/money";
import { Hr } from "@/components/Section";

// ── Style constants ────────────────────────────────────────────────────────────

const btnPrimary =
  "inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[12.5px] font-medium bg-foreground text-background";

const CURRENCIES = ["USD", "EUR", "AED", "RUB", "GBP", "JPY"];

// ── Field row ─────────────────────────────────────────────────────────────────

function FieldRow({
  label,
  children,
  first = false,
}: {
  label: string;
  children: React.ReactNode;
  first?: boolean;
}) {
  return (
    <div
      className={
        "grid grid-cols-[88px_1fr] items-center px-3 py-2.5" +
        (first ? "" : " border-t border-[#f0f0f1]")
      }
    >
      <span className="label">{label}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

// ── Mono ring progress ────────────────────────────────────────────────────────

function RingProgress({ fraction }: { fraction: number }) {
  const pct = Math.min(1, fraction);
  const r = 22;
  const circ = 2 * Math.PI * r;
  const dash = pct * circ;
  return (
    <svg
      width="56"
      height="56"
      viewBox="0 0 56 56"
      style={{ display: "block", transform: "rotate(-90deg)" }}
    >
      <circle cx="28" cy="28" r={r} fill="none" stroke="#f0f0f1" strokeWidth="6" />
      <circle
        cx="28"
        cy="28"
        r={r}
        fill="none"
        stroke="#0a0a0a"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${circ}`}
      />
    </svg>
  );
}

// ── Goal row ──────────────────────────────────────────────────────────────────

function GoalRow({
  name,
  progressMinor,
  targetMinor,
  currency,
  fraction,
  projectedHitDate,
  targetDate,
  onArchive,
}: {
  name: string;
  progressMinor: number;
  targetMinor: number;
  currency: string;
  fraction: number;
  projectedHitDate: string | null;
  targetDate: string | null;
  onArchive: () => void;
}) {
  const pct = Math.min(100, Math.round(fraction * 100));

  return (
    <div className="px-5 py-3">
      <div className="flex items-start gap-3">
        {/* Monochrome ring */}
        <div className="relative shrink-0" style={{ width: 56, height: 56 }}>
          <RingProgress fraction={fraction} />
          <div className="absolute inset-0 grid place-items-center">
            <span className="num text-[11px] font-semibold">{pct}%</span>
          </div>
        </div>

        <div className="flex-1 min-w-0 pt-1">
          <div className="flex items-start justify-between gap-2">
            <span className="text-[13px] font-semibold tracking-tight truncate">
              {name}
            </span>
            <button
              onClick={onArchive}
              className="w-6 h-6 flex items-center justify-center text-neutral-400 hover:text-neutral-700 transition-colors shrink-0"
              aria-label="Archive goal"
            >
              <Archive size={12} strokeWidth={1.75} />
            </button>
          </div>

          <div className="num text-[10.5px] text-neutral-500 mt-0.5">
            {formatAmount(progressMinor, currency)}
            <span className="text-neutral-300 mx-1">/</span>
            {formatAmount(targetMinor, currency)}
          </div>

          {/* Thin bar */}
          <div className="mt-2 h-[3px] rounded-full bg-neutral-100 overflow-hidden">
            <div
              className="h-full rounded-full bg-neutral-800"
              style={{ width: `${pct}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-[10px] text-neutral-400 mt-1.5 num">
            <span>
              {projectedHitDate
                ? `eta ${projectedHitDate}`
                : "no recent contributions"}
            </span>
            {targetDate && <span>target {targetDate}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Goals() {
  const nav = useNavigate();
  const qc = useQueryClient();

  const accsQuery = useQuery({
    queryKey: ["accs", false],
    queryFn: () => api.listAccounts(false),
    staleTime: 60_000,
  });

  const progQuery = useQuery({
    queryKey: ["goal-progress"],
    queryFn: () => api.goalProgress(),
    staleTime: 30_000,
  });

  const accounts = accsQuery.data ?? [];
  const goals = progQuery.data ?? [];

  // ── Form state ──────────────────────────────────────────────────────────────

  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [mode, setMode] = useState<"account_linked" | "contribution_tagged">(
    "account_linked"
  );
  const [accountId, setAccountId] = useState<number | "">("");
  const [targetDate, setTargetDate] = useState("");

  const createMut = useMutation({
    mutationFn: () =>
      api.createGoal({
        name,
        target_minor: toMinor(parseFloat(target) || 0, currency),
        currency,
        progress_mode: mode,
        account_id:
          mode === "account_linked" && typeof accountId === "number"
            ? accountId
            : null,
        target_date: targetDate || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["goal-progress"] });
      qc.invalidateQueries({ queryKey: ["goals"] });
      setName("");
      setTarget("");
      setTargetDate("");
      setAccountId("");
    },
  });

  const archiveMut = useMutation({
    mutationFn: (id: number) => api.archiveGoal(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["goal-progress"] });
      qc.invalidateQueries({ queryKey: ["goals"] });
    },
  });

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="pb-16">
      {/* ── Top bar ──────────────────────────────────────────────────────────── */}
      <div className="px-4 pt-4 pb-3 flex items-center justify-between">
        <button
          onClick={() => nav(-1)}
          className="w-8 h-8 flex items-center justify-center text-neutral-600 -ml-1"
          aria-label="Back"
        >
          <ChevronLeft size={20} strokeWidth={1.75} />
        </button>
        <span className="text-[13px] font-semibold tracking-tight">Goals</span>
        <button
          onClick={() =>
            document
              .getElementById("add-goal-form")
              ?.scrollIntoView({ behavior: "smooth" })
          }
          className="w-8 h-8 flex items-center justify-center text-neutral-600"
          aria-label="Add goal"
        >
          <Plus size={18} strokeWidth={1.75} />
        </button>
      </div>

      <Hr />

      {/* ── Goals list ──────────────────────────────────────────────────────── */}
      <div className="px-5 pt-5 pb-1">
        <div className="label mb-3">Active goals</div>
      </div>

      {progQuery.isLoading ? (
        <div className="px-5 py-3 label">Loading…</div>
      ) : goals.length === 0 ? (
        <div className="px-5 py-3 text-[12px] text-neutral-400">
          No goals yet.
        </div>
      ) : (
        <div className="divide-y divide-[#f0f0f1]">
          {goals.map((g) => (
            <GoalRow
              key={g.id}
              name={g.name}
              progressMinor={g.progress_minor}
              targetMinor={g.target_minor}
              currency={g.currency}
              fraction={g.fraction}
              projectedHitDate={g.projected_hit_date}
              targetDate={g.target_date}
              onArchive={() => archiveMut.mutate(g.id)}
            />
          ))}
        </div>
      )}

      <Hr />

      {/* ── Add goal form ────────────────────────────────────────────────────── */}
      <div id="add-goal-form" className="px-5 py-4">
        <div className="label mb-3">Add goal</div>
        <div className="border border-border rounded-md bg-white overflow-hidden">
          <FieldRow label="Name" first>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Emergency fund"
              className="text-[12.5px] bg-transparent border-0 outline-none w-full placeholder:text-neutral-300"
            />
          </FieldRow>

          <FieldRow label="Target">
            <input
              type="number"
              inputMode="decimal"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="0.00"
              className="num text-[12.5px] bg-transparent border-0 outline-none w-full placeholder:text-neutral-300"
            />
          </FieldRow>

          <FieldRow label="Currency">
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="num text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </FieldRow>

          <FieldRow label="Track via">
            <select
              value={mode}
              onChange={(e) =>
                setMode(
                  e.target.value as "account_linked" | "contribution_tagged"
                )
              }
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              <option value="account_linked">Savings account balance</option>
              <option value="contribution_tagged">Tagged contributions</option>
            </select>
          </FieldRow>

          {mode === "account_linked" && (
            <FieldRow label="Account">
              <select
                value={accountId}
                onChange={(e) =>
                  setAccountId(
                    e.target.value === "" ? "" : Number(e.target.value)
                  )
                }
                className="text-[12.5px] bg-transparent border-0 outline-none w-full"
              >
                <option value="">Select account…</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} · {a.currency}
                  </option>
                ))}
              </select>
            </FieldRow>
          )}

          <FieldRow label="Target date">
            <input
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
              className="num text-[12.5px] bg-transparent border-0 outline-none w-full"
            />
          </FieldRow>
        </div>

        <button
          className={btnPrimary + " mt-3 w-full justify-center"}
          onClick={() => {
            if (!name.trim() || !target) return;
            createMut.mutate();
          }}
          disabled={createMut.isPending || !name.trim() || !target}
        >
          <Plus size={13} strokeWidth={1.75} />
          {createMut.isPending ? "Adding…" : "Add goal"}
        </button>

        {createMut.isError && (
          <div className="mt-2 text-[11px] text-red-500">
            Error: {(createMut.error as Error).message}
          </div>
        )}
      </div>
    </div>
  );
}
