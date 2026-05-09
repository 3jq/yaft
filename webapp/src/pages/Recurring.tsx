import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Plus, Pause, Play, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { toMinor } from "@/lib/money";
import { Hr } from "@/components/Section";

// ── Style constants ────────────────────────────────────────────────────────────

const btnPrimary =
  "inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[12.5px] font-medium bg-foreground text-background";

const CURRENCIES = ["USD", "EUR", "AED", "RUB", "GBP", "JPY"];

const PRESETS = [
  { label: "Monthly · day 1", rrule: "FREQ=MONTHLY;BYMONTHDAY=1" },
  { label: "Monthly · day 15", rrule: "FREQ=MONTHLY;BYMONTHDAY=15" },
  { label: "Monthly · last day", rrule: "FREQ=MONTHLY;BYMONTHDAY=-1" },
  { label: "Weekly · Monday", rrule: "FREQ=WEEKLY;BYDAY=MO" },
  { label: "Bi-weekly · Monday", rrule: "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO" },
  { label: "Quarterly", rrule: "FREQ=MONTHLY;INTERVAL=3;BYMONTHDAY=1" },
  { label: "Yearly · Jan 1", rrule: "FREQ=YEARLY;BYMONTH=1;BYMONTHDAY=1" },
];

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

// ── Recurring row ─────────────────────────────────────────────────────────────

function RecurringRow({
  name,
  rrule,
  nextRunAt,
  lastRunAt,
  active,
  onPause,
  onResume,
  onDelete,
}: {
  name: string;
  rrule: string;
  nextRunAt: string | null;
  lastRunAt: string | null;
  active: number;
  onPause: () => void;
  onResume: () => void;
  onDelete: () => void;
}) {
  // Friendly label from preset or raw rrule
  const preset = PRESETS.find((p) => p.rrule === rrule);
  const rruleLabel = preset ? preset.label : rrule;

  return (
    <div className="px-5 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-semibold tracking-tight truncate">
              {name}
            </span>
            {!active && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 border border-neutral-300 rounded text-neutral-400 shrink-0">
                paused
              </span>
            )}
          </div>
          <div className="num text-[10.5px] text-neutral-400 mt-0.5">
            {rruleLabel}
          </div>
          <div className="num text-[10px] text-neutral-400 mt-1">
            next&nbsp;{nextRunAt ?? "—"}
            {lastRunAt && (
              <span>
                &nbsp;· last&nbsp;{lastRunAt}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0 mt-0.5">
          {active ? (
            <button
              onClick={onPause}
              className="w-7 h-7 flex items-center justify-center text-neutral-400 hover:text-neutral-700 transition-colors"
              aria-label="Pause"
            >
              <Pause size={13} strokeWidth={1.75} />
            </button>
          ) : (
            <button
              onClick={onResume}
              className="w-7 h-7 flex items-center justify-center text-neutral-400 hover:text-neutral-700 transition-colors"
              aria-label="Resume"
            >
              <Play size={13} strokeWidth={1.75} />
            </button>
          )}
          <button
            onClick={onDelete}
            className="w-7 h-7 flex items-center justify-center text-neutral-400 hover:text-neutral-700 transition-colors"
            aria-label="Delete"
          >
            <Trash2 size={13} strokeWidth={1.75} />
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Recurring() {
  const nav = useNavigate();
  const qc = useQueryClient();

  const accsQuery = useQuery({
    queryKey: ["accs", false],
    queryFn: () => api.listAccounts(false),
    staleTime: 60_000,
  });

  const catsQuery = useQuery({
    queryKey: ["cats"],
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  });

  const listQuery = useQuery({
    queryKey: ["recurring"],
    queryFn: () => api.listRecurring(),
    staleTime: 30_000,
  });

  const accounts = accsQuery.data ?? [];
  const cats = catsQuery.data ?? [];
  const rules = listQuery.data ?? [];

  // ── Form state ──────────────────────────────────────────────────────────────

  const [name, setName] = useState("");
  const [rrule, setRrule] = useState(PRESETS[0].rrule);
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [acctId, setAcctId] = useState<number | "">("");
  const [catId, setCatId] = useState<number | "">("");
  const [nextRun, setNextRun] = useState("");

  const createMut = useMutation({
    mutationFn: () =>
      api.createRecurring({
        name,
        rrule,
        template_json: JSON.stringify({
          kind: "expense",
          amount_minor: toMinor(parseFloat(amount) || 0, currency),
          currency,
          account_id: typeof acctId === "number" ? acctId : null,
          category_id: typeof catId === "number" ? catId : null,
          merchant: null,
          note: name,
        }),
        next_run_at: nextRun || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recurring"] });
      setName("");
      setAmount("");
      setNextRun("");
      setAcctId("");
      setCatId("");
    },
  });

  const pauseMut = useMutation({
    mutationFn: (id: number) => api.pauseRecurring(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recurring"] }),
  });

  const resumeMut = useMutation({
    mutationFn: (id: number) => api.resumeRecurring(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recurring"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteRecurring(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recurring"] }),
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
        <span className="text-[13px] font-semibold tracking-tight">
          Recurring
        </span>
        <button
          onClick={() =>
            document
              .getElementById("add-recurring-form")
              ?.scrollIntoView({ behavior: "smooth" })
          }
          className="w-8 h-8 flex items-center justify-center text-neutral-600"
          aria-label="Add rule"
        >
          <Plus size={18} strokeWidth={1.75} />
        </button>
      </div>

      <Hr />

      {/* ── Rules list ───────────────────────────────────────────────────────── */}
      <div className="px-5 pt-5 pb-1">
        <div className="label mb-3">Scheduled rules</div>
      </div>

      {listQuery.isLoading ? (
        <div className="px-5 py-3 label">Loading…</div>
      ) : rules.length === 0 ? (
        <div className="px-5 py-3 text-[12px] text-neutral-400">
          No rules yet.
        </div>
      ) : (
        <div className="divide-y divide-[#f0f0f1]">
          {rules.map((r) => (
            <RecurringRow
              key={r.id}
              name={r.name}
              rrule={r.rrule}
              nextRunAt={r.next_run_at}
              lastRunAt={r.last_run_at}
              active={r.active}
              onPause={() => pauseMut.mutate(r.id)}
              onResume={() => resumeMut.mutate(r.id)}
              onDelete={() => deleteMut.mutate(r.id)}
            />
          ))}
        </div>
      )}

      <Hr />

      {/* ── Add rule form ────────────────────────────────────────────────────── */}
      <div id="add-recurring-form" className="px-5 py-4">
        <div className="label mb-3">Add rule</div>
        <div className="border border-border rounded-md bg-white overflow-hidden">
          <FieldRow label="Name" first>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Netflix subscription"
              className="text-[12.5px] bg-transparent border-0 outline-none w-full placeholder:text-neutral-300"
            />
          </FieldRow>

          <FieldRow label="Schedule">
            <select
              value={rrule}
              onChange={(e) => setRrule(e.target.value)}
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              {PRESETS.map((p) => (
                <option key={p.rrule} value={p.rrule}>
                  {p.label}
                </option>
              ))}
            </select>
          </FieldRow>

          <FieldRow label="Amount">
            <input
              type="number"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
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

          <FieldRow label="Account">
            <select
              value={acctId}
              onChange={(e) =>
                setAcctId(e.target.value === "" ? "" : Number(e.target.value))
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

          <FieldRow label="Category">
            <select
              value={catId}
              onChange={(e) =>
                setCatId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              <option value="">Select category…</option>
              {cats
                .filter((c) => c.kind === "expense" && !c.archived)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.emoji ? `${c.emoji} ` : ""}
                    {c.name}
                  </option>
                ))}
            </select>
          </FieldRow>

          <FieldRow label="First run">
            <input
              type="date"
              value={nextRun}
              onChange={(e) => setNextRun(e.target.value)}
              className="num text-[12.5px] bg-transparent border-0 outline-none w-full"
            />
          </FieldRow>
        </div>

        <button
          className={btnPrimary + " mt-3 w-full justify-center"}
          onClick={() => {
            if (!name.trim() || !amount || !acctId) return;
            createMut.mutate();
          }}
          disabled={createMut.isPending || !name.trim() || !amount || !acctId}
        >
          <Plus size={13} strokeWidth={1.75} />
          {createMut.isPending ? "Adding…" : "Add rule"}
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
