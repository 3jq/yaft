import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  MoreVertical,
  MessageSquareQuote,
  RotateCw,
  Split,
  Trash2,
  Flag,
} from "lucide-react";
import { api, Category } from "@/lib/api";
import { fromMinor, toMinor, formatBase } from "@/lib/money";
import { Hr } from "@/components/Section";

// ── Button style constants ────────────────────────────────────────────────────

const btnPrimary =
  "inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[12.5px] font-medium bg-foreground text-background";
const btnGhost =
  "inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[12.5px] font-medium bg-transparent text-foreground border border-border";
const btnDanger =
  "inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[12.5px] font-medium bg-transparent text-foreground border border-[#d4d4d4]";

// ── Kind segmented control ────────────────────────────────────────────────────

type Kind = "income" | "expense" | "transfer";

function KindControl({
  value,
  onChange,
}: {
  value: Kind;
  onChange: (k: Kind) => void;
}) {
  const opts: { k: Kind; label: string }[] = [
    { k: "income", label: "Income" },
    { k: "expense", label: "Expense" },
    { k: "transfer", label: "Transfer" },
  ];
  return (
    <div className="flex rounded-md border border-border overflow-hidden">
      {opts.map(({ k, label }) => (
        <button
          key={k}
          onClick={() => onChange(k)}
          className={
            "flex-1 text-[11.5px] font-medium py-1.5 transition-colors " +
            (value === k
              ? "bg-foreground text-background"
              : "bg-transparent text-neutral-500 hover:bg-neutral-50")
          }
        >
          {label}
        </button>
      ))}
    </div>
  );
}

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

// ── Category label helper ─────────────────────────────────────────────────────

function catLabel(cat: Category, allCats: Category[]): string {
  if (cat.parent_id != null) {
    const parent = allCats.find((c) => c.id === cat.parent_id);
    if (parent) return `${parent.name} / ${cat.name}`;
  }
  return cat.name;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function TransactionEdit() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const qc = useQueryClient();

  const txId = Number(id);

  // ── Queries ──────────────────────────────────────────────────────────────────

  const txQuery = useQuery({
    queryKey: ["tx", txId],
    queryFn: () => api.getTransaction(txId),
    enabled: !isNaN(txId),
  });

  const accQuery = useQuery({
    queryKey: ["accs"],
    queryFn: () => api.listAccounts(),
    staleTime: 60_000,
  });

  const catQuery = useQuery({
    queryKey: ["cats"],
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  });

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.getSettings(),
    staleTime: 300_000,
  });

  const tx = txQuery.data;
  const accounts = accQuery.data ?? [];
  const categories = catQuery.data ?? [];
  const baseCurrency = settingsQuery.data?.base_currency ?? tx?.currency ?? "USD";

  // ── Local form state ─────────────────────────────────────────────────────────

  const [amountStr, setAmountStr] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [kind, setKind] = useState<Kind>("expense");
  const [occurredAt, setOccurredAt] = useState("");
  const [accountId, setAccountId] = useState<number | "">("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [merchant, setMerchant] = useState("");
  const [note, setNote] = useState("");

  // Initialise form once tx is loaded
  const [initialised, setInitialised] = useState(false);
  useEffect(() => {
    if (tx && !initialised) {
      setAmountStr(String(fromMinor(Math.abs(tx.amount_minor), tx.currency)));
      setCurrency(tx.currency);
      setKind((tx.kind as Kind) ?? "expense");
      // Format datetime-local value: "YYYY-MM-DDTHH:MM"
      setOccurredAt(tx.occurred_at.slice(0, 16));
      setAccountId(tx.account_id);
      setCategoryId(tx.category_id ?? "");
      setMerchant(tx.merchant ?? "");
      setNote(tx.note ?? "");
      setInitialised(true);
    }
  }, [tx, initialised]);

  // ── Derived: amount_minor for save ───────────────────────────────────────────

  const parsedAmount = parseFloat(amountStr) || 0;
  const amountMinorForSave = toMinor(parsedAmount, currency);

  // For expense / transfer, store as positive minor; sign convention is `kind`
  const effectiveAmountMinor =
    kind === "income" ? amountMinorForSave : -amountMinorForSave;

  // ── Base estimate display ────────────────────────────────────────────────────

  const showBaseEst = currency !== baseCurrency && tx != null;
  const baseEstStr = showBaseEst
    ? `≈ −${formatBase(tx!.base_amount_minor, baseCurrency)}`
    : "";

  // ── Mutations ────────────────────────────────────────────────────────────────

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["txs"] });
    qc.invalidateQueries({ queryKey: ["summary"] });
    qc.invalidateQueries({ queryKey: ["tx", txId] });
  };

  const saveMut = useMutation({
    mutationFn: () =>
      api.patchTransaction(txId, {
        amount_minor: effectiveAmountMinor,
        currency,
        account_id: accountId !== "" ? Number(accountId) : undefined,
        category_id: categoryId !== "" ? Number(categoryId) : null,
        occurred_at: occurredAt ? new Date(occurredAt).toISOString() : undefined,
        merchant: merchant || null,
        note: note || null,
      }),
    onSuccess: () => {
      invalidate();
      nav(-1);
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => api.deleteTransaction(txId),
    onSuccess: () => {
      invalidate();
      nav(-1);
    },
  });

  // ── Loading / error states ───────────────────────────────────────────────────

  if (txQuery.isLoading) {
    return <div className="p-5 label">Loading…</div>;
  }

  if (!tx) {
    return <div className="p-5 label">Transaction not found.</div>;
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="relative pb-32">
      {/* ── Top bar ──────────────────────────────────────────────────────────── */}
      <div className="px-4 pt-4 pb-3 flex items-center justify-between">
        <button
          onClick={() => nav(-1)}
          className="w-8 h-8 flex items-center justify-center text-neutral-600 -ml-1"
          aria-label="Back"
        >
          <ChevronLeft size={20} strokeWidth={1.75} />
        </button>

        <span className="num text-[13px] text-neutral-400">
          <span className="text-neutral-300">#</span>
          {id}
        </span>

        <button
          className="w-8 h-8 flex items-center justify-center text-neutral-500"
          aria-label="More options"
        >
          <MoreVertical size={18} strokeWidth={1.75} />
        </button>
      </div>

      <Hr />

      {/* ── Raw input quote ───────────────────────────────────────────────────── */}
      {tx.raw_input && (
        <>
          <div className="px-5 py-3.5 flex items-start gap-2.5">
            <MessageSquareQuote
              size={14}
              strokeWidth={1.75}
              className="text-neutral-400 mt-0.5 shrink-0"
            />
            <p className="text-[12px] text-neutral-400 italic leading-relaxed">
              {tx.raw_input}
            </p>
          </div>
          <Hr />
        </>
      )}

      {/* ── Amount header ─────────────────────────────────────────────────────── */}
      <div className="px-5 pt-4 pb-3 space-y-3">
        {/* Amount row */}
        <div className="flex items-center gap-2">
          <div className="flex items-baseline gap-1 flex-1 min-w-0">
            <span className="label shrink-0">Amount</span>
            <input
              type="number"
              inputMode="decimal"
              value={amountStr}
              onChange={(e) => setAmountStr(e.target.value)}
              className="num bg-transparent border-0 outline-none flex-1 min-w-0 text-right"
              style={{ fontSize: 34, fontWeight: 500, letterSpacing: "-0.02em" }}
              placeholder="0.00"
            />
          </div>

          {/* Currency select */}
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="num text-[12px] text-neutral-500 bg-transparent border border-border rounded px-1.5 py-1 outline-none shrink-0"
          >
            {["USD", "EUR", "GBP", "AED", "RUB", "CHF", "CAD", "AUD", "CNY", "INR", "JPY", "TRY", "PLN"].map(
              (c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              )
            )}
          </select>

          {/* Base estimate */}
          {showBaseEst && (
            <span className="num text-[11.5px] text-neutral-400 shrink-0">
              {baseEstStr}
            </span>
          )}
        </div>

        {/* Kind segmented control */}
        <KindControl value={kind} onChange={setKind} />
      </div>

      <Hr />

      {/* ── Field group form ─────────────────────────────────────────────────── */}
      <div className="px-5 py-3">
        <div className="border border-border rounded-md bg-white overflow-hidden">
          {/* Date */}
          <FieldRow label="Date" first>
            <input
              type="datetime-local"
              value={occurredAt}
              onChange={(e) => setOccurredAt(e.target.value)}
              className="num text-[12.5px] bg-transparent border-0 outline-none w-full"
            />
          </FieldRow>

          {/* Account */}
          <FieldRow label="Account">
            <select
              value={accountId}
              onChange={(e) =>
                setAccountId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              <option value="">— select —</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </FieldRow>

          {/* Category */}
          <FieldRow label="Category">
            <select
              value={categoryId}
              onChange={(e) =>
                setCategoryId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              <option value="">— none —</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {catLabel(c, categories)}
                </option>
              ))}
            </select>
          </FieldRow>

          {/* Merchant */}
          <FieldRow label="Merchant">
            <input
              type="text"
              value={merchant}
              onChange={(e) => setMerchant(e.target.value)}
              placeholder="—"
              className="text-[12.5px] bg-transparent border-0 outline-none w-full placeholder:text-neutral-300"
            />
          </FieldRow>

          {/* Note */}
          <FieldRow label="Note">
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="—"
              className="text-[12.5px] bg-transparent border-0 outline-none w-full placeholder:text-neutral-300"
            />
          </FieldRow>

          {/* Tag/Goal — placeholder */}
          <FieldRow label="Tag goal">
            <select className="text-[12.5px] bg-transparent border-0 outline-none w-full text-neutral-400">
              <option value="">—</option>
            </select>
          </FieldRow>
        </div>
      </div>

      {/* ── Confidence + flag row ─────────────────────────────────────────────── */}
      <div className="px-5 py-2 flex items-center justify-between">
        <span className="text-[11px] text-neutral-400">
          {tx.confidence != null && (
            <>
              Confidence{" "}
              <span className="num font-medium text-neutral-600">
                {Math.round(tx.confidence * 100)}%
              </span>
            </>
          )}
          {tx.source && (
            <span className="text-neutral-300 mx-1.5">·</span>
          )}
          {tx.source && (
            <span className="text-neutral-400">{tx.source}</span>
          )}
        </span>
        <button className="flex items-center gap-1 text-[11px] border border-border rounded-full px-2.5 py-1 text-neutral-500">
          <Flag size={10} strokeWidth={1.75} />
          Flag for review
        </button>
      </div>

      <Hr />

      {/* ── Action buttons ────────────────────────────────────────────────────── */}
      <div className="px-5 py-4 space-y-2">
        <div className="flex gap-2">
          <button
            className={btnGhost + " flex-1 justify-center"}
            onClick={() => alert("Retry will be wired with the bot retry endpoint")}
          >
            <RotateCw size={13} strokeWidth={1.75} />
            Retry parse
          </button>
          <button
            className={btnGhost + " flex-1 justify-center"}
            onClick={() => nav(-1)}
          >
            <Split size={13} strokeWidth={1.75} />
            Split
          </button>
        </div>
        <button
          className={btnDanger + " w-full justify-center"}
          onClick={() => {
            if (confirm("Delete this transaction?")) {
              deleteMut.mutate();
            }
          }}
          disabled={deleteMut.isPending}
        >
          <Trash2 size={13} strokeWidth={1.75} />
          {deleteMut.isPending ? "Deleting…" : "Delete transaction"}
        </button>
      </div>

      {/* ── Sticky save bar ───────────────────────────────────────────────────── */}
      <div className="fixed bottom-14 inset-x-0 bg-background/95 backdrop-blur border-t border-border px-5 py-3 flex items-center gap-2 z-20">
        <button
          className={btnGhost + " flex-1 justify-center"}
          onClick={() => nav(-1)}
        >
          Cancel
        </button>
        <button
          className={btnPrimary + " flex-1 justify-center"}
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending}
        >
          {saveMut.isPending ? "Saving…" : "Save"}
        </button>
      </div>

      {/* Save error */}
      {saveMut.isError && (
        <div className="px-5 pb-2 text-[11px] text-red-500">
          Save failed: {(saveMut.error as Error).message}
        </div>
      )}
    </div>
  );
}
