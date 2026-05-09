import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";
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

// ── Mono progress bar ─────────────────────────────────────────────────────────

function ProgressBar({ fraction }: { fraction: number }) {
  const pct = Math.min(100, Math.round(fraction * 100));
  return (
    <div className="mt-2 h-[3px] rounded-full bg-neutral-100 overflow-hidden">
      <div
        className="h-full rounded-full bg-neutral-800"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ── Budget row ────────────────────────────────────────────────────────────────

function BudgetRow({
  catName,
  spentMinor,
  amountMinor,
  currency,
  fraction,
  onDelete,
}: {
  catName: string;
  spentMinor: number;
  amountMinor: number;
  currency: string;
  fraction: number;
  onDelete: () => void;
}) {
  const pct = Math.min(100, Math.round(fraction * 100));

  return (
    <div className="px-5 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold tracking-tight truncate">
            {catName}
          </div>
          <div className="num text-[10.5px] text-neutral-400 mt-0.5">
            {formatAmount(spentMinor, currency)}
            <span className="text-neutral-300 mx-1">/</span>
            {formatAmount(amountMinor, currency)}
            <span className="text-neutral-400 ml-2">· {pct}%</span>
          </div>
          <ProgressBar fraction={fraction} />
        </div>
        <button
          onClick={onDelete}
          className="w-7 h-7 flex items-center justify-center text-neutral-400 hover:text-neutral-700 transition-colors shrink-0 mt-0.5"
          aria-label="Delete budget"
        >
          <Trash2 size={13} strokeWidth={1.75} />
        </button>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Budgets() {
  const nav = useNavigate();
  const qc = useQueryClient();

  const catsQuery = useQuery({
    queryKey: ["cats"],
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  });

  const progQuery = useQuery({
    queryKey: ["budget-progress"],
    queryFn: () => api.budgetProgress(),
    staleTime: 30_000,
  });

  const cats = catsQuery.data ?? [];
  const progress = progQuery.data ?? [];

  const catName = Object.fromEntries(cats.map((c) => [c.id, c.name]));
  const expenseCats = cats.filter((c) => c.kind === "expense" && !c.archived);

  // ── Add budget form ────────────────────────────────────────────────────────

  const [catId, setCatId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("USD");

  const createMut = useMutation({
    mutationFn: () =>
      api.createBudget({
        category_id: Number(catId),
        amount_minor: toMinor(parseFloat(amount) || 0, currency),
        currency,
        alert_thresholds: [0.8, 1.0],
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget-progress"] });
      qc.invalidateQueries({ queryKey: ["budgets"] });
      setCatId("");
      setAmount("");
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteBudget(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget-progress"] });
      qc.invalidateQueries({ queryKey: ["budgets"] });
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
        <span className="text-[13px] font-semibold tracking-tight">Budgets</span>
        <button
          onClick={() =>
            document
              .getElementById("add-budget-form")
              ?.scrollIntoView({ behavior: "smooth" })
          }
          className="w-8 h-8 flex items-center justify-center text-neutral-600"
          aria-label="Add budget"
        >
          <Plus size={18} strokeWidth={1.75} />
        </button>
      </div>

      <Hr />

      {/* ── This month ──────────────────────────────────────────────────────── */}
      <div className="px-5 pt-5 pb-1">
        <div className="label mb-3">This month</div>
      </div>

      {progQuery.isLoading ? (
        <div className="px-5 py-3 label">Loading…</div>
      ) : progress.length === 0 ? (
        <div className="px-5 py-3 text-[12px] text-neutral-400">
          No budgets yet.
        </div>
      ) : (
        <div className="divide-y divide-[#f0f0f1]">
          {progress.map((p) => (
            <BudgetRow
              key={p.budget_id}
              catName={catName[p.category_id] ?? `Category #${p.category_id}`}
              spentMinor={p.spent_minor}
              amountMinor={p.amount_minor}
              currency={p.currency}
              fraction={p.fraction}
              onDelete={() => deleteMut.mutate(p.budget_id)}
            />
          ))}
        </div>
      )}

      <Hr />

      {/* ── Add budget form ──────────────────────────────────────────────────── */}
      <div id="add-budget-form" className="px-5 py-4">
        <div className="label mb-3">Add budget</div>
        <div className="border border-border rounded-md bg-white overflow-hidden">
          <FieldRow label="Category" first>
            <select
              value={catId}
              onChange={(e) =>
                setCatId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              <option value="">Select category…</option>
              {expenseCats.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.emoji ? `${c.emoji} ` : ""}
                  {c.name}
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
        </div>

        <button
          className={btnPrimary + " mt-3 w-full justify-center"}
          onClick={() => {
            if (!catId || !amount) return;
            createMut.mutate();
          }}
          disabled={createMut.isPending || !catId || !amount}
        >
          <Plus size={13} strokeWidth={1.75} />
          {createMut.isPending ? "Adding…" : "Add budget"}
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
