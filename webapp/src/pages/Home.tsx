import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, Tx } from "@/lib/api";
import { formatBase, formatAmount } from "@/lib/money";
import { Hr } from "@/components/Section";
import { Sparkbar } from "@/components/Sparkbar";
import { Donut } from "@/components/Donut";
import { Heatmap, buildMonthHeatmap } from "@/components/Heatmap";
import { Pill } from "@/components/Pill";

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtTime(iso: string): string {
  // occurred_at is ISO-8601; take HH:MM portion
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function fmtBalanceWhole(m: number, c: string): { whole: string; frac: string } {
  const e = c === "JPY" || c === "KRW" ? 0 : 2;
  const sign = m < 0 ? "−" : "";
  const n = Math.abs(m);
  const whole = Math.floor(n / 10 ** e).toLocaleString("en-US");
  const frac = e === 0 ? "" : (n % 10 ** e).toString().padStart(e, "0");
  return { whole: `${sign}${whole}`, frac };
}

// currency symbol
function sym(c: string): string {
  switch (c.toUpperCase()) {
    case "USD": case "AUD": case "CAD": return "$";
    case "EUR": return "€";
    case "GBP": return "£";
    case "RUB": return "₽";
    case "JPY": case "CNY": return "¥";
    default: return "";
  }
}

// ── component ────────────────────────────────────────────────────────────────

export default function Home() {
  const nav = useNavigate();
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.getSummary });
  const txQuery = useQuery({ queryKey: ["transactions"], queryFn: () => api.listTransactions(false) });
  const goalsQuery = useQuery({ queryKey: ["goal-progress"], queryFn: api.goalProgress });

  if (summary.isLoading || txQuery.isLoading) {
    return <div className="p-5 label">Loading…</div>;
  }

  const s = summary.data!;
  const allTx = (txQuery.data ?? []).filter((t) => !t.deleted_at);
  const base = s.base_currency;

  // ── Net worth (base) ────────────────────────────────────────────────────────
  const baseBalances = s.account_balances.filter((a) => a.currency === base);
  const otherBalances = s.account_balances.filter((a) => a.currency !== base);
  const netWorthMinor = baseBalances.reduce((acc, a) => acc + a.balance_minor, 0);
  const netWorthStr = formatBase(netWorthMinor, base);

  // Split whole / fractional for display
  // e.g. "$12,847.50" → "$12,847" and ".50"
  const dotIdx = netWorthStr.lastIndexOf(".");
  const nwWhole = dotIdx !== -1 ? netWorthStr.slice(0, dotIdx) : netWorthStr;
  const nwFrac = dotIdx !== -1 ? netWorthStr.slice(dotIdx) : "";

  // Other-currency footnote
  const otherGroups: Record<string, { total: number; count: number }> = {};
  for (const a of otherBalances) {
    if (!otherGroups[a.currency]) otherGroups[a.currency] = { total: 0, count: 0 };
    otherGroups[a.currency].total += a.balance_minor;
    otherGroups[a.currency].count += 1;
  }
  const otherFootnotes = Object.entries(otherGroups).map(([ccy, { total, count }]) => {
    const sign = total >= 0 ? "+" : "−";
    const abs = formatAmount(Math.abs(total), ccy);
    return `${sign} ${abs} in ${count} account${count > 1 ? "s" : ""}`;
    // TODO: Phase 4 will add server-side conversion to base ccy.
  });

  // ── KPI strip ───────────────────────────────────────────────────────────────
  const spentMinor = s.total_expense_minor;
  const savedMinor = s.total_income_minor - s.total_expense_minor;

  // ── Month label / current date ───────────────────────────────────────────────
  const now = new Date();
  const year = now.getFullYear();
  const month0 = now.getMonth();
  const monthLabel = now.toLocaleString("en-US", { month: "long" });
  const monthYear = `${monthLabel} ${year}`;
  const todayLabel = now.toLocaleString("en-US", { month: "long", day: "numeric" });
  const todayIso = now.toISOString().slice(0, 10);

  // ── Heatmap ─────────────────────────────────────────────────────────────────
  const expenseTx = allTx.filter((t) => t.kind === "expense");
  const dailyByIso: Record<string, number> = {};
  for (const t of expenseTx) {
    const d = t.occurred_at.slice(0, 10);
    if (!dailyByIso[d]) dailyByIso[d] = 0;
    dailyByIso[d] += t.base_amount_minor;
  }
  const { weeks, todayIndex, max: hmMax } = buildMonthHeatmap(year, month0, dailyByIso);

  const daysWithSpend = Object.keys(dailyByIso).filter((d) => {
    const [dy, dm] = d.split("-").map(Number);
    return dm - 1 === month0 && dy === year;
  });
  const totalMonthSpendMinor = daysWithSpend.reduce((acc, d) => acc + (dailyByIso[d] ?? 0), 0);
  const avgPerDay = daysWithSpend.length > 0 ? Math.round(totalMonthSpendMinor / daysWithSpend.length) : 0;
  const avgStr = formatBase(avgPerDay, base);

  // ── Categories donut ────────────────────────────────────────────────────────
  const topCats = s.by_category.slice(0, 5);
  const donutSlices = topCats.map((c) => ({ value: c.expense_minor, label: c.name }));
  // donut center: drop cents to keep it short and readable inside the ring
  const donutCenterTop = formatBase(Math.round(spentMinor / 100) * 100, base).replace(/\.00$/, "");

  // ── Today section ───────────────────────────────────────────────────────────
  const todayTx = allTx.filter((t) => t.occurred_at.slice(0, 10) === todayIso);

  // Group today's expense amounts by currency, pick dominant
  const todayExpense = todayTx.filter((t) => t.kind === "expense");
  const byCurrency: Record<string, number> = {};
  for (const t of todayExpense) {
    if (!byCurrency[t.currency]) byCurrency[t.currency] = 0;
    byCurrency[t.currency] += t.amount_minor;
  }
  // Dominant currency = one with highest absolute total
  let dominantCurrency = base;
  let dominantTotal = 0;
  for (const [ccy, total] of Object.entries(byCurrency)) {
    if (total > dominantTotal) { dominantTotal = total; dominantCurrency = ccy; }
  }
  const todayDomTotal = byCurrency[dominantCurrency] ?? 0;
  const todayBaseMinor = todayExpense.reduce((acc, t) => acc + t.base_amount_minor, 0);
  const todayBaseStr = formatBase(-todayBaseMinor, base);

  // ── Accounts ─────────────────────────────────────────────────────────────────
  const accounts = s.account_balances;
  const colCount = accounts.length >= 3 ? 3 : accounts.length === 2 ? 2 : 1;

  return (
    <div>
      {/* ── Top bar ─────────────────────────────────────────────────────────── */}
      <div className="px-5 pt-4 pb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-sm" style={{ background: "#0a0a0a" }} />
          <span className="text-[13px] font-semibold tracking-tight">Finance</span>
          <Pill>{monthYear}</Pill>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="text-[#737373] grid place-items-center w-7 h-7"
            style={{ outline: "none" }}
            aria-label="Search"
            onClick={() => nav("/transactions")}
          >
            <Search size={18} strokeWidth={1.75} />
          </button>
          <button
            className="w-7 h-7 rounded-full border border-[#e5e5e5] grid place-items-center text-[11px] font-medium"
            style={{ outline: "none" }}
            aria-label="Settings"
            onClick={() => nav("/settings")}
          >
            A
          </button>
        </div>
      </div>

      <div className="hr" />

      {/* ── HERO (net worth) ─────────────────────────────────────────────────── */}
      <div className="px-5 pt-7 pb-5 text-center">
        <div className="label">Net worth</div>
        <div className="num text-[52px] font-semibold leading-none tracking-tight mt-3">
          {nwWhole}
          <span className="text-[26px] text-neutral-400 font-normal">{nwFrac}</span>
        </div>
        {otherFootnotes.map((fn, i) => (
          <div key={i} className="num text-[11px] text-muted-foreground mt-1">{fn}</div>
        ))}
        {/* TODO: Phase 4 real 7-day delta endpoint */}
        <div className="num text-[14px] text-neutral-500 mt-3">+$342 · +2.7% · 7d</div>
        <div className="mt-5 flex justify-center">
          <Sparkbar values={[3, 5.5, 4.2, 6.8, 5.8, 7.8, 7.2, 9.2]} />
        </div>
      </div>

      <Hr />

      {/* ── KPI strip ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 px-5 py-3.5 text-center divide-x divide-[#e5e5e5]">
        <div>
          <div className="label">Spent</div>
          <div className="num text-[13px] font-medium mt-1">{formatBase(-spentMinor, base)}</div>
        </div>
        <div>
          <div className="label">Saved</div>
          <div className="num text-[13px] font-medium mt-1">
            {savedMinor >= 0 ? "+" : ""}
            {formatBase(savedMinor, base)}
          </div>
        </div>
        <div>
          <div className="label">Goal</div>
          {/* TODO: Phase 4 — real goal % from settings */}
          <div className="num text-[13px] font-medium mt-1">32%</div>
        </div>
      </div>

      <Hr />

      {/* ── HEATMAP ─────────────────────────────────────────────────────────── */}
      <div className="px-5 py-4">
        <div className="flex items-baseline justify-between mb-3">
          <div className="label">Daily spend · {monthLabel}</div>
          <span className="num text-[11px] text-neutral-500">avg&nbsp;{avgStr}/d</span>
        </div>
        <Heatmap
          weeks={weeks}
          todayIndex={todayIndex}
          max={hmMax}
          legendLess="less"
          legendMore="more"
        />
      </div>

      <Hr />

      {/* ── CATEGORIES ──────────────────────────────────────────────────────── */}
      <div className="px-5 py-5">
        <div className="flex items-center justify-between mb-4">
          <div className="label">Categories</div>
          <a className="text-[11px] text-[#525252] border-b border-[#d4d4d4] pb-px cursor-pointer" onClick={() => nav("/categories")}>all →</a>
        </div>
        <div className="grid gap-5 items-center" style={{ gridTemplateColumns: "auto 1fr" }}>
          <div className="relative" style={{ outline: "none" }}>
            <Donut
              slices={donutSlices.length > 0 ? donutSlices : [{ value: 1, label: "—" }]}
              centerTop={donutCenterTop}
              centerBottom={`/ ${formatBase(120000, base).replace(/\.00$/, "")}`}
              /* TODO: Phase 4 — real budget from settings; hardcoded $1,200 for now */
            />
          </div>
          <div className="text-[12.5px] space-y-1.5">
            {topCats.map((cat, i) => (
              <div key={cat.category_id ?? i} className="flex items-baseline justify-between">
                <span>
                  <span className="num text-neutral-400 mr-1.5">{i + 1}</span>
                  {cat.name || "Uncategorised"}
                </span>
                <span className="num text-neutral-700">{formatBase(cat.expense_minor, base)}</span>
              </div>
            ))}
            {topCats.length === 0 && (
              <div className="text-muted-foreground text-[11px]">No expenses this month</div>
            )}
          </div>
        </div>
      </div>

      <Hr />

      {/* ── TODAY ───────────────────────────────────────────────────────────── */}
      <div className="px-5 py-5">
        <div className="flex items-baseline justify-between mb-3">
          <span className="text-[15px] font-semibold tracking-tight">
            Today{" "}
            <span className="text-neutral-400 font-normal text-[12px]">· {todayLabel}</span>
          </span>
          <div className="text-right">
            {todayExpense.length > 0 ? (
              <>
                <div className="num text-[18px] font-semibold leading-none">
                  {/* Show dominant currency total */}
                  {formatAmount(-todayDomTotal, dominantCurrency)}
                </div>
                {dominantCurrency !== base && (
                  <div className="num text-[11px] text-neutral-500 leading-none mt-1">
                    ≈ {todayBaseStr}
                  </div>
                )}
              </>
            ) : (
              <div className="num text-[13px] text-muted-foreground">—</div>
            )}
          </div>
        </div>

        <div className="-mx-2">
          {todayTx.length === 0 && (
            <div className="px-2 py-2 text-[12px] text-muted-foreground">No transactions today</div>
          )}
          {todayTx.map((t) => (
            <TxRow key={t.id} tx={t} base={base} />
          ))}
        </div>
      </div>

      <Hr />

      {/* ── ACCOUNTS ────────────────────────────────────────────────────────── */}
      <div className="px-5 py-5">
        <div className="flex items-center justify-between mb-3">
          <div className="label">Accounts</div>
          <a className="text-[11px] text-[#525252] border-b border-[#d4d4d4] pb-px cursor-pointer" onClick={() => nav("/accounts")}>manage →</a>
        </div>
        <div
          className="grid gap-2"
          style={{ gridTemplateColumns: `repeat(${colCount}, 1fr)` }}
        >
          {accounts.map((acct) => {
            const { whole, frac } = fmtBalanceWhole(acct.balance_minor, acct.currency);
            const currSym = sym(acct.currency);
            return (
              <button
                key={acct.account_id}
                onClick={() => nav("/accounts")}
                style={{
                  border: "1px solid #e5e5e5",
                  borderRadius: 8,
                  padding: "10px 11px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  background: "#fff",
                  textAlign: "left",
                  outline: "none",
                }}
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] font-medium truncate">{acct.name}</span>
                  <span className="num text-[9.5px] text-neutral-400 ml-1 shrink-0">{acct.currency}</span>
                </div>
                <div className="num text-[14px] font-semibold leading-tight">
                  {currSym}{whole}
                  <span className="text-neutral-400 text-[10px] font-normal">
                    {frac ? `.${frac}` : acct.currency !== "JPY" && acct.currency !== "KRW" ? "" : ""}
                  </span>
                </div>
                {/* Placeholder sparkline — TODO: Phase 4 real sparkline data */}
                <div className="mt-1" style={{ outline: "none" }}>
                  <svg width="100%" height="14" viewBox="0 0 80 14" preserveAspectRatio="none">
                    <polyline
                      points="0,9 10,8 20,7 30,8 40,5 50,7 60,5 70,4 80,3"
                      fill="none"
                      stroke="#0a0a0a"
                      strokeWidth="1.2"
                    />
                  </svg>
                </div>
                {/* TODO: Phase 4 — real 30-day delta */}
                <div className="num text-[10px] text-neutral-500">+$0 / 30d</div>
              </button>
            );
          })}
        </div>
      </div>

      <Hr />

      {/* ── GOALS ───────────────────────────────────────────────────────────── */}
      <div className="px-5 py-5 mb-2">
        <div className="flex items-center justify-between mb-3">
          <div className="label">Goals</div>
          <a className="text-[11px] text-[#525252] border-b border-[#d4d4d4] pb-px cursor-pointer" onClick={() => nav("/goals")}>+ new</a>
        </div>
        {(goalsQuery.data ?? []).length === 0 ? (
          <div className="text-[12px] text-neutral-500">No active goals. <a className="border-b border-[#d4d4d4] pb-px cursor-pointer" onClick={() => nav("/goals")}>Create one →</a></div>
        ) : (
          <div className="flex flex-col gap-4">
            {(goalsQuery.data ?? []).slice(0, 3).map((g) => {
              const pct = Math.max(0, Math.min(100, Math.round(g.fraction * 100)));
              const C = 2 * Math.PI * 22; // circumference
              const dash = (pct / 100) * C;
              return (
                <button
                  key={g.id}
                  onClick={() => nav("/goals")}
                  className="flex items-center gap-3 text-left w-full"
                >
                  <div className="relative shrink-0" style={{ width: 56, height: 56, outline: "none" }}>
                    <svg width="56" height="56" viewBox="0 0 56 56" style={{ display: "block", transform: "rotate(-90deg)" }}>
                      <circle cx="28" cy="28" r="22" fill="none" stroke="#f0f0f1" strokeWidth="6" />
                      <circle
                        cx="28" cy="28" r="22" fill="none" stroke="#0a0a0a" strokeWidth="6"
                        strokeLinecap="round" strokeDasharray={`${dash} ${C - dash}`}
                      />
                    </svg>
                    <div className="absolute inset-0 grid place-items-center">
                      <span className="num text-[11px] font-semibold">{pct}%</span>
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-[13px] font-medium truncate">{g.name}</span>
                    </div>
                    <div className="num text-[11.5px] text-neutral-500 mt-1">
                      {formatBase(g.progress_minor, g.currency)}<span className="text-neutral-400">&nbsp;/&nbsp;</span>{formatBase(g.target_minor, g.currency)}&nbsp;{g.currency}
                    </div>
                    <div className="relative mt-2 h-[5px] bg-[#f0f0f1] rounded-full overflow-hidden">
                      <div className="absolute inset-y-0 left-0 rounded-full" style={{ background: "#0a0a0a", width: `${pct}%` }} />
                      <span className="absolute inset-y-0 w-px" style={{ left: "25%", background: pct > 25 ? "#fafafa" : "#d4d4d4" }} />
                      <span className="absolute inset-y-0 w-px" style={{ left: "50%", background: pct > 50 ? "#fafafa" : "#d4d4d4" }} />
                      <span className="absolute inset-y-0 w-px" style={{ left: "75%", background: pct > 75 ? "#fafafa" : "#d4d4d4" }} />
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-neutral-500 mt-2 num">
                      <span>{g.target_date ? `target ${g.target_date}` : "no target date"}</span>
                      <span>{g.projected_hit_date ? `eta ${g.projected_hit_date}` : "—"}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Transaction row ───────────────────────────────────────────────────────────

function TxRow({ tx, base }: { tx: Tx; base: string }) {
  const nav = useNavigate();
  const title = tx.note || tx.merchant || "—";
  const time = fmtTime(tx.occurred_at);

  // Format amount with sign
  let amtStr: string;
  if (tx.kind === "transfer") {
    // show ± prefix
    const abs = formatAmount(Math.abs(tx.amount_minor), tx.currency);
    amtStr = `±${abs}`;
  } else if (tx.kind === "expense") {
    amtStr = formatAmount(-tx.amount_minor, tx.currency);
  } else {
    // income
    amtStr = `+${formatAmount(tx.amount_minor, tx.currency)}`;
  }

  const showBaseEst = tx.currency !== base && tx.kind !== "transfer";
  const baseEstStr = tx.kind === "expense"
    ? `≈ ${formatBase(-tx.base_amount_minor, base)}`
    : `≈ ${formatBase(tx.base_amount_minor, base)}`;

  return (
    <div
      className="px-2 py-2 rounded-md cursor-pointer hover:bg-muted"
      onClick={() => nav(`/transactions/${tx.id}`)}
      style={{
        display: "grid",
        gridTemplateColumns: "1fr auto",
        columnGap: 12,
        rowGap: 2,
      }}
    >
      <span className="text-[13px] font-medium">{title}</span>
      <span className={`num text-[13px] text-right ${tx.kind === "transfer" ? "text-neutral-500" : ""}`}>
        {amtStr}
      </span>
      <span className="text-[11px] text-neutral-500">
        <span className="num">{time}</span>
        {tx.kind !== "transfer" && (
          <>
            <span className="text-neutral-300 mx-1">·</span>
            {/* account name not in tx — show kind as fallback */}
            <span>{tx.kind}</span>
          </>
        )}
        {tx.kind === "transfer" && (
          <>
            <span className="text-neutral-300 mx-1">·</span>
            Transfer
          </>
        )}
      </span>
      {showBaseEst ? (
        <span className="num text-[10.5px] text-neutral-400 text-right">{baseEstStr}</span>
      ) : (
        <span />
      )}
    </div>
  );
}
