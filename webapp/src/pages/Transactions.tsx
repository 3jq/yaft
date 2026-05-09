import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, Filter, AlertTriangle } from "lucide-react";
import { api, Tx, Account, Category } from "@/lib/api";
import { formatBase, formatAmount } from "@/lib/money";
import { Hr } from "@/components/Section";
import { Pill } from "@/components/Pill";

// ── Inline Chip component ─────────────────────────────────────────────────────

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="shrink-0 text-[11px] px-[10px] py-1 rounded-full border whitespace-nowrap"
      style={
        active
          ? { background: "#0a0a0a", color: "#fafafa", borderColor: "#0a0a0a" }
          : { background: "#fafafa", color: "#525252", borderColor: "#e5e5e5" }
      }
    >
      {children}
    </button>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function dateSectionLabel(isoDate: string, todayIso: string, yesterdayIso: string): string {
  if (isoDate === todayIso) {
    const d = new Date(isoDate + "T12:00:00");
    const day = DAY_NAMES[d.getDay()];
    const mon = MONTH_NAMES[d.getMonth()];
    return `Today · ${day}, ${mon} ${d.getDate()}`;
  }
  if (isoDate === yesterdayIso) {
    const d = new Date(isoDate + "T12:00:00");
    const day = DAY_NAMES[d.getDay()];
    const mon = MONTH_NAMES[d.getMonth()];
    return `Yesterday · ${day}, ${mon} ${d.getDate()}`;
  }
  const d = new Date(isoDate + "T12:00:00");
  const day = DAY_NAMES[d.getDay()];
  const mon = MONTH_NAMES[d.getMonth()];
  return `${day}, ${mon} ${d.getDate()}`;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Transactions() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState<string>("All");
  const [search, setSearch] = useState("");

  const txQuery = useQuery({
    queryKey: ["txs"],
    queryFn: () => api.listTransactions(false),
    staleTime: 30_000,
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

  const allTx: Tx[] = useMemo(
    () => (txQuery.data ?? []).filter((t) => !t.deleted_at),
    [txQuery.data]
  );
  const accounts: Account[] = accQuery.data ?? [];
  const categories: Category[] = catQuery.data ?? [];

  // Derive today / yesterday ISO dates
  const now = new Date();
  const todayIso = now.toISOString().slice(0, 10);
  const yesterdayDate = new Date(now);
  yesterdayDate.setDate(yesterdayDate.getDate() - 1);
  const yesterdayIso = yesterdayDate.toISOString().slice(0, 10);

  // Month label for pill
  const monthYear = now.toLocaleString("en-US", { month: "long", year: "numeric" });

  // Review count (confidence < 0.5)
  const reviewCount = allTx.filter((t) => (t.confidence ?? 1) < 0.5).length;

  // Top 5 categories by expense count
  const topCategoryIds = useMemo(() => {
    const counts: Record<number, number> = {};
    for (const t of allTx) {
      if (t.category_id != null) {
        counts[t.category_id] = (counts[t.category_id] ?? 0) + 1;
      }
    }
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([id]) => Number(id));
  }, [allTx]);

  // Account map
  const accountMap = useMemo(() => {
    const m: Record<number, Account> = {};
    for (const a of accounts) m[a.id] = a;
    return m;
  }, [accounts]);

  // Category map
  const categoryMap = useMemo(() => {
    const m: Record<number, Category> = {};
    for (const c of categories) m[c.id] = c;
    return m;
  }, [categories]);

  // Group-id sibling counts
  const groupSiblingCount = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const t of allTx) {
      if (t.group_id) counts[t.group_id] = (counts[t.group_id] ?? 0) + 1;
    }
    return counts;
  }, [allTx]);

  // Base currency from first account or fallback
  const baseCurrency = useMemo(() => {
    // Prefer non-transfer tx that has currency info — just use first tx currency as proxy
    // The summary endpoint has base_currency but we're not fetching it here;
    // use the most common currency among transactions as a proxy.
    if (allTx.length === 0) return "USD";
    const freq: Record<string, number> = {};
    for (const t of allTx) freq[t.currency] = (freq[t.currency] ?? 0) + 1;
    return Object.entries(freq).sort((a, b) => b[1] - a[1])[0][0];
  }, [allTx]);

  // Seven-days-ago ISO
  const sevenDaysAgoDate = new Date(now);
  sevenDaysAgoDate.setDate(sevenDaysAgoDate.getDate() - 6);
  const sevenDaysAgoIso = sevenDaysAgoDate.toISOString().slice(0, 10);

  // Filtering
  const filtered = useMemo(() => {
    let base = allTx;

    // Apply chip filter
    if (activeFilter === "All") {
      // no additional filter
    } else if (activeFilter === "Today") {
      base = base.filter((t) => t.occurred_at.slice(0, 10) === todayIso);
    } else if (activeFilter === "This week") {
      base = base.filter((t) => t.occurred_at.slice(0, 10) >= sevenDaysAgoIso);
    } else if (activeFilter.startsWith("Review")) {
      base = base.filter((t) => (t.confidence ?? 1) < 0.5);
    } else if (activeFilter.startsWith("acc:")) {
      const id = Number(activeFilter.slice(4));
      base = base.filter((t) => t.account_id === id);
    } else if (activeFilter.startsWith("cat:")) {
      const id = Number(activeFilter.slice(4));
      base = base.filter((t) => t.category_id === id);
    }

    // Search
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      base = base.filter(
        (t) =>
          (t.note ?? "").toLowerCase().includes(q) ||
          (t.merchant ?? "").toLowerCase().includes(q)
      );
    }

    return base;
  }, [allTx, activeFilter, search, todayIso, sevenDaysAgoIso]);

  // Summary strip values
  const summarySpent = filtered
    .filter((t) => t.kind === "expense")
    .reduce((acc, t) => acc + t.base_amount_minor, 0);
  const summaryIncome = filtered
    .filter((t) => t.kind === "income")
    .reduce((acc, t) => acc + t.base_amount_minor, 0);

  // Group by date descending
  const dateGroups = useMemo(() => {
    const groups: Record<string, Tx[]> = {};
    for (const t of filtered) {
      const d = t.occurred_at.slice(0, 10);
      if (!groups[d]) groups[d] = [];
      groups[d].push(t);
    }
    // Sort dates descending
    const sortedDates = Object.keys(groups).sort((a, b) => (a > b ? -1 : 1));
    return sortedDates.map((date) => ({
      date,
      txs: groups[date].sort((a, b) =>
        a.occurred_at > b.occurred_at ? -1 : 1
      ),
    }));
  }, [filtered]);

  if (txQuery.isLoading) {
    return <div className="p-5 label">Loading…</div>;
  }

  return (
    <div className="relative">
      {/* ── Top bar ──────────────────────────────────────────────────────────── */}
      <div className="px-5 pt-4 pb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-sm" style={{ background: "#0a0a0a" }} />
          <span className="text-[13px] font-semibold tracking-tight">Transactions</span>
          <Pill>{monthYear}</Pill>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="text-[#737373] grid place-items-center w-7 h-7"
            style={{ outline: "none" }}
            aria-label="Filter"
          >
            <Filter size={18} strokeWidth={1.75} />
          </button>
          <div className="w-7 h-7 rounded-full border border-[#e5e5e5] grid place-items-center text-[11px] font-medium">
            A
          </div>
        </div>
      </div>

      <div className="hr" />

      {/* ── Search ──────────────────────────────────────────────────────────── */}
      <div className="px-5 pt-3">
        <div
          className="flex items-center gap-2 px-3 py-2"
          style={{
            background: "#f4f4f5",
            border: "1px solid #e5e5e5",
            borderRadius: 6,
          }}
        >
          <Search size={14} strokeWidth={1.75} className="text-neutral-400 shrink-0" />
          <input
            className="bg-transparent flex-1 text-[12.5px] outline-none placeholder:text-neutral-400"
            placeholder="Search transactions, merchants, notes…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* ── Filter chips ─────────────────────────────────────────────────────── */}
      <div
        className="px-5 pt-3 pb-3 flex gap-2 overflow-x-auto scrollx"
        style={{ scrollbarWidth: "none" }}
      >
        <Chip active={activeFilter === "All"} onClick={() => setActiveFilter("All")}>
          All
        </Chip>
        <Chip active={activeFilter === "Today"} onClick={() => setActiveFilter("Today")}>
          Today
        </Chip>
        <Chip active={activeFilter === "This week"} onClick={() => setActiveFilter("This week")}>
          This week
        </Chip>
        <Chip
          active={activeFilter.startsWith("Review")}
          onClick={() => setActiveFilter(`Review (${reviewCount})`)}
        >
          <span className="flex items-center gap-1">
            <AlertTriangle size={11} strokeWidth={1.75} />
            Review ({reviewCount})
          </span>
        </Chip>
        {accounts.map((a) => (
          <Chip
            key={`acc:${a.id}`}
            active={activeFilter === `acc:${a.id}`}
            onClick={() => setActiveFilter(`acc:${a.id}`)}
          >
            {a.name}
          </Chip>
        ))}
        {topCategoryIds.map((catId) => {
          const cat = categoryMap[catId];
          if (!cat) return null;
          return (
            <Chip
              key={`cat:${catId}`}
              active={activeFilter === `cat:${catId}`}
              onClick={() => setActiveFilter(`cat:${catId}`)}
            >
              {cat.name}
            </Chip>
          );
        })}
      </div>

      <div className="hr" />

      {/* ── Summary strip ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 mx-5 my-3 text-center divide-x divide-[#e5e5e5] border border-[#e5e5e5] rounded-md">
        <div className="py-2">
          <div className="label">Showing</div>
          <div className="num text-[12px] font-medium mt-0.5">{filtered.length} tx</div>
        </div>
        <div className="py-2">
          <div className="label">Spent</div>
          <div className="num text-[12px] font-medium mt-0.5">
            {summarySpent > 0 ? `−${formatBase(summarySpent, baseCurrency)}` : "—"}
          </div>
        </div>
        <div className="py-2">
          <div className="label">Income</div>
          <div className="num text-[12px] font-medium mt-0.5">
            {summaryIncome > 0 ? `+${formatBase(summaryIncome, baseCurrency)}` : "—"}
          </div>
        </div>
      </div>

      <div className="hr" />

      {/* ── Date sections ────────────────────────────────────────────────────── */}
      {dateGroups.length === 0 && (
        <div className="px-5 py-6 text-[12px] text-neutral-400 text-center">
          No transactions found
        </div>
      )}
      {dateGroups.map(({ date, txs }) => {
        const label = dateSectionLabel(date, todayIso, yesterdayIso);

        // Per-date total: expenses negative, income positive, in base currency
        const dateTotal = txs.reduce((acc, t) => {
          if (t.kind === "expense") return acc - t.base_amount_minor;
          if (t.kind === "income") return acc + t.base_amount_minor;
          return acc;
        }, 0);

        let dateTotalStr = "—";
        if (dateTotal !== 0) {
          const sign = dateTotal < 0 ? "−" : "+";
          dateTotalStr = `${sign}${formatBase(Math.abs(dateTotal), baseCurrency)}`;
        }

        return (
          <div key={date}>
            {/* Date header */}
            <div className="px-5 pt-5 pb-2 flex items-baseline justify-between">
              <span className="text-[15px] font-semibold tracking-tight">
                {label.includes("·") ? (
                  <>
                    {label.split("·")[0].trim()}{" "}
                    <span className="text-neutral-400 font-normal text-[12px]">
                      · {label.split("·")[1].trim()}
                    </span>
                  </>
                ) : (
                  label
                )}
              </span>
              <span className="num text-[11px] text-neutral-500">{dateTotalStr}</span>
            </div>

            <Hr />

            {/* Tx rows */}
            <div className="px-3 py-2">
              {txs.map((t) => (
                <TxRow
                  key={t.id}
                  tx={t}
                  base={baseCurrency}
                  accountMap={accountMap}
                  categoryMap={categoryMap}
                  groupSiblingCount={groupSiblingCount}
                  onClick={() => navigate(`/transactions/${t.id}`)}
                />
              ))}
            </div>
          </div>
        );
      })}

      {/* Manual web-add is intentionally not in Phase 3 — primary input is the bot
          (voice/text). Floating + removed; will return in a later phase if useful. */}
    </div>
  );
}

// ── Transaction row ───────────────────────────────────────────────────────────

function TxRow({
  tx,
  base,
  accountMap,
  categoryMap,
  groupSiblingCount,
  onClick,
}: {
  tx: Tx;
  base: string;
  accountMap: Record<number, Account>;
  categoryMap: Record<number, Category>;
  groupSiblingCount: Record<string, number>;
  onClick: () => void;
}) {
  const time = fmtTime(tx.occurred_at);
  const isLowConfidence = (tx.confidence ?? 1) < 0.5;

  // Title
  let title: React.ReactNode;
  if (tx.kind === "transfer") {
    // "From → To" using account names
    // For transfers the account_id is the source; there's no dest in the tx model,
    // so we show account name + "Transfer" or try to find paired tx via group_id.
    // Since the API Tx type has only one account_id, render "AccountName → Transfer"
    const accName = accountMap[tx.account_id]?.name ?? `Acct #${tx.account_id}`;
    title = (
      <span className="text-neutral-700">{accName} → Transfer</span>
    );
  } else {
    const raw = tx.note ?? tx.merchant ?? "(no note)";
    const splitCount =
      tx.group_id && groupSiblingCount[tx.group_id] && groupSiblingCount[tx.group_id] > 1
        ? groupSiblingCount[tx.group_id]
        : null;

    title = (
      <>
        {raw}
        {splitCount && (
          <span className="text-neutral-400 font-normal text-[12px]">
            {" "}· split ({splitCount})
          </span>
        )}
        {isLowConfidence && (
          <AlertTriangle
            size={11}
            strokeWidth={1.75}
            className="inline ml-1.5 text-amber-600 relative"
            style={{ top: -1 }}
          />
        )}
      </>
    );
  }

  // Amount
  let amtStr: string;
  let amtClass = "";
  if (tx.kind === "transfer") {
    amtStr = `±${formatAmount(Math.abs(tx.amount_minor), tx.currency)}`;
    amtClass = "text-neutral-500";
  } else if (tx.kind === "expense") {
    amtStr = `−${formatAmount(Math.abs(tx.amount_minor), tx.currency)}`;
  } else {
    amtStr = `+${formatAmount(tx.amount_minor, tx.currency)}`;
  }

  // Base estimate (only for non-base-currency transactions)
  const showBaseEst = tx.currency !== base && tx.kind !== "transfer";
  const baseEstStr =
    tx.kind === "expense"
      ? `≈ −${formatBase(tx.base_amount_minor, base)}`
      : `≈ +${formatBase(tx.base_amount_minor, base)}`;

  // Meta line: time · account · category
  const accName = accountMap[tx.account_id]?.name;
  const catName = tx.category_id ? categoryMap[tx.category_id]?.name : null;

  const metaParts: React.ReactNode[] = [];
  metaParts.push(<span className="num" key="time">{time}</span>);
  if (tx.kind === "transfer") {
    metaParts.push(<Sep key="s1" />, <span key="kind">Transfer</span>);
  } else {
    if (accName) metaParts.push(<Sep key="s1" />, <span key="acc">{accName}</span>);
    if (catName) metaParts.push(<Sep key="s2" />, <span key="cat">{catName}</span>);
    if (isLowConfidence) metaParts.push(<Sep key="s3" />, <span key="review" className="text-amber-600">review</span>);
  }

  return (
    <button
      onClick={onClick}
      className="w-full px-2 py-2 rounded-md text-left hover:bg-[#f4f4f5] transition-colors"
      style={{
        display: "grid",
        gridTemplateColumns: "1fr auto",
        columnGap: 12,
        rowGap: 2,
      }}
    >
      <span className="text-[13px] font-medium">{title}</span>
      <span className={`num text-[13px] text-right ${amtClass}`}>{amtStr}</span>
      <span className="text-[11px] text-neutral-500 flex items-center gap-0 flex-wrap min-w-0">
        {metaParts}
      </span>
      {showBaseEst ? (
        <span className="num text-[10.5px] text-neutral-400 text-right">{baseEstStr}</span>
      ) : (
        <span />
      )}
    </button>
  );
}

function Sep() {
  return <span className="text-neutral-300 mx-1">·</span>;
}
