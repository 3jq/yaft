const STOPS = ["#f0f0f1", "#e5e5e5", "#d4d4d4", "#a3a3a3", "#737373", "#404040", "#0a0a0a"];

function colorFor(value: number, max: number): string {
  if (max <= 0 || value <= 0) return "#f0f0f1";
  const t = Math.min(1, value / max);
  const idx = Math.max(1, Math.min(STOPS.length - 1, Math.ceil(t * (STOPS.length - 1))));
  return STOPS[idx];
}

export function Heatmap({
  weeks,
  todayIndex,
  max,
  legendLess = "less",
  legendMore = "more",
}: {
  weeks: { dateLabel: string; cells: (number | null)[] }[];
  todayIndex: [number, number] | null;
  max: number;
  legendLess?: string;
  legendMore?: string;
}) {
  return (
    <div>
      <div className="grid items-center mb-1.5" style={{ gridTemplateColumns: "42px 1fr" }}>
        <span></span>
        <div className="flex justify-between text-[8.5px] text-muted-foreground num">
          {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
            <span key={i} className="inline-block text-center" style={{ width: 18 }}>
              {d}
            </span>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        {weeks.map((w, wi) => (
          <div key={wi} className="grid items-center" style={{ gridTemplateColumns: "42px 1fr" }}>
            <span className="num text-[9.5px] text-muted-foreground text-right pr-2">{w.dateLabel}</span>
            <div className="flex justify-between">
              {w.cells.map((v, di) => {
                const isToday = todayIndex && todayIndex[0] === wi && todayIndex[1] === di;
                const bg = v === null ? "#fff" : colorFor(v, max);
                return (
                  <div
                    key={di}
                    style={{
                      width: 18,
                      height: 18,
                      background: bg,
                      border: "1px solid #f0f0f1",
                      outline: isToday ? "1.5px solid #0a0a0a" : undefined,
                      outlineOffset: isToday ? 1 : undefined,
                    }}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-end gap-1.5 mt-3 text-[9px] text-muted-foreground">
        <span>{legendLess}</span>
        {["#f0f0f1", "#a3a3a3", "#404040", "#0a0a0a"].map((c, i) => (
          <span key={i} style={{ width: 11, height: 11, background: c, border: "1px solid #f0f0f1", display: "inline-block" }} />
        ))}
        <span>{legendMore}</span>
      </div>
    </div>
  );
}

/** Derive heatmap weeks from a flat list of (date → minor) entries for the current month. */
export function buildMonthHeatmap(
  year: number,
  month0: number,
  dailyByIso: Record<string, number>
): {
  weeks: { dateLabel: string; cells: (number | null)[] }[];
  todayIndex: [number, number] | null;
  max: number;
} {
  // First Monday on or before the 1st
  const first = new Date(Date.UTC(year, month0, 1));
  // JS getUTCDay: 0=Sun..6=Sat. Convert to 0=Mon..6=Sun
  const dow = (first.getUTCDay() + 6) % 7;
  const start = new Date(first);
  start.setUTCDate(first.getUTCDate() - dow);
  const lastDay = new Date(Date.UTC(year, month0 + 1, 0)).getUTCDate();
  const today = new Date();
  const todayIso = today.toISOString().slice(0, 10);
  let max = 0;
  let todayIndex: [number, number] | null = null;

  const weeks: { dateLabel: string; cells: (number | null)[] }[] = [];
  // 5 or 6 weeks
  for (let w = 0; w < 6; w++) {
    const cells: (number | null)[] = [];
    let weekStart: string | null = null;
    for (let d = 0; d < 7; d++) {
      const cur = new Date(start);
      cur.setUTCDate(start.getUTCDate() + w * 7 + d);
      const iso = cur.toISOString().slice(0, 10);
      const inMonth = cur.getUTCMonth() === month0 && cur.getUTCDate() <= lastDay;
      if (d === 0) {
        const ml = cur.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
        weekStart = `${ml} ${cur.getUTCDate()}`;
      }
      if (!inMonth) {
        cells.push(null);
      } else {
        const v = dailyByIso[iso] ?? 0;
        cells.push(v);
        if (v > max) max = v;
        if (iso === todayIso) todayIndex = [w, d];
      }
    }
    if (cells.every((c) => c === null)) break;
    weeks.push({ dateLabel: weekStart!, cells });
  }
  return { weeks, todayIndex, max };
}
