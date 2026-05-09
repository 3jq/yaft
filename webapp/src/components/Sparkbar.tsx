const COLORS = ["#d4d4d4", "#d4d4d4", "#a3a3a3", "#a3a3a3", "#737373", "#737373", "#404040", "#0a0a0a"];

export function Sparkbar({ values }: { values: number[] }) {
  if (!values.length) return null;
  const max = Math.max(...values, 1);
  return (
    <div className="inline-flex items-end gap-1 h-7">
      {values.map((v, i) => (
        <span
          key={i}
          className="w-1.5"
          style={{
            height: `${Math.max(8, (v / max) * 100)}%`,
            background: COLORS[Math.min(COLORS.length - 1, i)],
            display: "inline-block",
          }}
        />
      ))}
    </div>
  );
}
