import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";
import { api, Account } from "@/lib/api";
import { formatAmount, formatBase, toMinor } from "@/lib/money";
import { Hr } from "@/components/Section";

type BalanceInfo = {
  current_minor: number;
  prev_30d_minor: number;
};

// ── Button style constants ────────────────────────────────────────────────────

const btnPrimary =
  "inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[12.5px] font-medium bg-foreground text-background";

// ── Field row (matches TransactionEdit styling) ───────────────────────────────

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

// ── Account row ───────────────────────────────────────────────────────────────

function AccountRow({
  account,
  balance,
  totalAbsBalanceMinor,
  onDelete,
  deleting,
}: {
  account: Account;
  balance: BalanceInfo | undefined;
  totalAbsBalanceMinor: number;
  onDelete: () => void;
  deleting: boolean;
}) {
  const balMinor = balance?.current_minor ?? account.opening_balance_minor;
  const prevMinor = balance?.prev_30d_minor ?? account.opening_balance_minor;
  const deltaMinor = balMinor - prevMinor;
  const shareRaw =
    totalAbsBalanceMinor > 0 ? Math.abs(balMinor) / totalAbsBalanceMinor : 0;
  const sharePct = Math.max(0, Math.min(1, shareRaw));
  const pctLabel = `${Math.round(sharePct * 100)}% of net`;
  const formattedBal = formatAmount(balMinor, account.currency);

  let deltaLabel: string;
  if (deltaMinor === 0) {
    deltaLabel = "flat / 30d";
  } else {
    const sign = deltaMinor > 0 ? "+" : "−";
    deltaLabel = `${sign}${formatAmount(Math.abs(deltaMinor), account.currency).replace(/^[−-]/, "")} / 30d`;
  }

  return (
    <div className="w-full px-5 py-3 hover:bg-neutral-50 transition-colors">
      {/* Top row */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[13px] font-semibold tracking-tight truncate">
            {account.name}
          </div>
          <div className="num text-[10.5px] text-neutral-400 mt-0.5 truncate">
            {account.kind} · {account.currency}
          </div>
        </div>
        <div className="flex items-start gap-2 shrink-0">
          <div className="text-right">
            <div className="num text-[13px] font-medium">{formattedBal}</div>
            <div className="num text-[10.5px] text-neutral-400 mt-0.5">{deltaLabel}</div>
          </div>
          <button
            onClick={onDelete}
            disabled={deleting}
            aria-label="Delete account"
            className="w-7 h-7 -mr-1 grid place-items-center text-neutral-400 hover:text-red-500 disabled:opacity-50"
          >
            <Trash2 size={14} strokeWidth={1.75} />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-2.5 h-[3px] rounded-full bg-neutral-100 overflow-hidden">
        <div
          className="h-full rounded-full bg-neutral-800"
          style={{ width: `${Math.round(sharePct * 100)}%` }}
        />
      </div>
      <div className="num text-[10px] text-neutral-400 mt-1">{pctLabel}</div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const CURRENCIES = ["USD", "EUR", "AED", "RUB", "GBP"];
const KINDS = ["cash", "bank", "card", "savings", "crypto", "business", "other"];

export default function Accounts() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const addFormRef = useRef<HTMLDivElement>(null);

  // ── Queries ──────────────────────────────────────────────────────────────────

  const accsQuery = useQuery({
    queryKey: ["accs", false],
    queryFn: () => api.listAccounts(false),
    staleTime: 30_000,
  });

  const archivedQuery = useQuery({
    queryKey: ["accs-archived"],
    queryFn: () => api.listAccounts(true),
    staleTime: 60_000,
  });

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: api.getSettings,
    staleTime: 300_000,
  });

  const summaryQuery = useQuery({
    queryKey: ["summary"],
    queryFn: api.getSummary,
    staleTime: 30_000,
  });

  const accounts: Account[] = accsQuery.data ?? [];
  const archivedAccounts: Account[] = archivedQuery.data ?? [];
  const base = settingsQuery.data?.base_currency ?? "USD";

  // ── Live balances from summary ───────────────────────────────────────────────

  const balanceById = new Map<number, BalanceInfo>();
  for (const b of summaryQuery.data?.account_balances ?? []) {
    balanceById.set(b.account_id, {
      current_minor: b.balance_minor,
      prev_30d_minor: b.balance_30d_ago_minor,
    });
  }
  const liveBalance = (a: Account): number =>
    balanceById.get(a.id)?.current_minor ?? a.opening_balance_minor;

  // ── Net assets calc ───────────────────────────────────────────────────────────

  const baseAccounts = accounts.filter((a) => a.currency === base);
  const nonBaseAccounts = accounts.filter((a) => a.currency !== base);
  const netMinor = baseAccounts.reduce((sum, a) => sum + liveBalance(a), 0);
  const totalAbsBalanceMinor = accounts.reduce(
    (sum, a) => sum + Math.abs(liveBalance(a)),
    0
  );

  const currencySet = new Set(accounts.map((a) => a.currency));
  const currencyCount = currencySet.size;

  // ── Add account form ──────────────────────────────────────────────────────────

  const [name, setName] = useState("");
  const [kind, setKind] = useState("cash");
  const [currency, setCurrency] = useState("USD");
  const [openingStr, setOpeningStr] = useState("0");

  const createMut = useMutation({
    mutationFn: () =>
      api.createAccount({
        name,
        kind,
        currency,
        opening_balance_minor: toMinor(parseFloat(openingStr) || 0, currency),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accs"] });
      qc.invalidateQueries({ queryKey: ["summary"] });
      setName("");
      setKind("cash");
      setCurrency("USD");
      setOpeningStr("0");
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteAccount(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accs"] });
      qc.invalidateQueries({ queryKey: ["summary"] });
    },
  });

  const handleDelete = (a: Account) => {
    if (!confirm(`Delete account "${a.name}"? This cannot be undone.`)) return;
    deleteMut.mutate(a.id, {
      onError: (err) => {
        const msg = (err as Error).message;
        if (msg.includes("409")) {
          alert(
            `Can't delete "${a.name}" — it has transactions or is linked to a goal. Archive it instead.`
          );
        } else {
          alert(`Delete failed: ${msg}`);
        }
      },
    });
  };

  // ── Render ───────────────────────────────────────────────────────────────────

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

        <span className="text-[13px] font-semibold tracking-tight">Accounts</span>

        <button
          onClick={() =>
            addFormRef.current?.scrollIntoView({ behavior: "smooth" })
          }
          className="w-8 h-8 flex items-center justify-center text-neutral-600"
          aria-label="Add account"
        >
          <Plus size={18} strokeWidth={1.75} />
        </button>
      </div>

      <Hr />

      {/* ── Net assets hero ──────────────────────────────────────────────────── */}
      <div className="px-5 py-5">
        <div className="label mb-1.5">Net assets · {base}</div>
        <div
          className="num font-semibold tracking-tight"
          style={{ fontSize: 34, letterSpacing: "-0.02em" }}
        >
          {formatBase(netMinor, base)}
        </div>
        {nonBaseAccounts.length > 0 && (
          <div className="text-[11px] text-neutral-400 mt-1">
            + {nonBaseAccounts.length} non-base account
            {nonBaseAccounts.length > 1 ? "s" : ""}
          </div>
        )}
        <div className="num text-[11px] text-neutral-400 mt-2">
          {accounts.length} account{accounts.length !== 1 ? "s" : ""} ·{" "}
          {currencyCount} currenc{currencyCount !== 1 ? "ies" : "y"}
        </div>
      </div>

      <Hr />

      {/* ── Account list ─────────────────────────────────────────────────────── */}
      {accsQuery.isLoading ? (
        <div className="px-5 py-4 label">Loading…</div>
      ) : accounts.length === 0 ? (
        <div className="px-5 py-4 text-[12px] text-neutral-400">
          No accounts yet.
        </div>
      ) : (
        <div className="divide-y divide-[#f0f0f1]">
          {accounts.map((a) => (
            <AccountRow
              key={a.id}
              account={a}
              balance={balanceById.get(a.id)}
              totalAbsBalanceMinor={totalAbsBalanceMinor}
              onDelete={() => handleDelete(a)}
              deleting={deleteMut.isPending && deleteMut.variables === a.id}
            />
          ))}
        </div>
      )}

      <Hr />

      {/* ── Add account form ─────────────────────────────────────────────────── */}
      <div ref={addFormRef} className="px-5 py-4">
        <div className="label mb-3">Add account</div>
        <div className="border border-border rounded-md bg-white overflow-hidden">
          <FieldRow label="Name" first>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My account"
              className="text-[12.5px] bg-transparent border-0 outline-none w-full placeholder:text-neutral-300"
            />
          </FieldRow>

          <FieldRow label="Type">
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value)}
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
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

          <FieldRow label="Opening bal.">
            <input
              type="number"
              inputMode="decimal"
              value={openingStr}
              onChange={(e) => setOpeningStr(e.target.value)}
              className="num text-[12.5px] bg-transparent border-0 outline-none w-full"
            />
          </FieldRow>
        </div>

        <button
          className={btnPrimary + " mt-3 w-full justify-center"}
          onClick={() => {
            if (!name.trim()) return;
            createMut.mutate();
          }}
          disabled={createMut.isPending || !name.trim()}
        >
          <Plus size={13} strokeWidth={1.75} />
          {createMut.isPending ? "Adding…" : "Add account"}
        </button>

        {createMut.isError && (
          <div className="mt-2 text-[11px] text-red-500">
            Error: {(createMut.error as Error).message}
          </div>
        )}
      </div>

      <Hr />

      {/* ── Archived footer ───────────────────────────────────────────────────── */}
      <div className="px-5 py-4">
        {archivedAccounts.length > 0 ? (
          <button className="text-[12px] text-neutral-500 underline underline-offset-2">
            Archived · show {archivedAccounts.length} →
          </button>
        ) : (
          <span className="text-[12px] text-neutral-400">Archived · 0</span>
        )}
      </div>
    </div>
  );
}
