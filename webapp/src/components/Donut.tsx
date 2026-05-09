const STROKES = ["#0a0a0a", "#404040", "#737373", "#a3a3a3", "#d4d4d4"];

export function Donut({
  slices,
  centerTop,
  centerBottom,
  size = 104,
  stroke = 9,
  radius = 42,
}: {
  slices: { value: number; label: string }[];
  centerTop: string;
  centerBottom?: string;
  size?: number;
  stroke?: number;
  radius?: number;
}) {
  const C = 2 * Math.PI * radius;
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  let offset = 0;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#f0f0f1" strokeWidth={stroke} />
        {slices.slice(0, 5).map((s, i) => {
          const len = (s.value / total) * C;
          const dasharray = `${len} ${C - len}`;
          const dashoffset = -offset;
          offset += len;
          return (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={STROKES[i]}
              strokeWidth={stroke}
              strokeDasharray={dasharray}
              strokeDashoffset={dashoffset}
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="num text-[15px] font-semibold leading-none">{centerTop}</div>
        {centerBottom && (
          <div className="text-[9px] uppercase tracking-wider text-muted-foreground mt-1">{centerBottom}</div>
        )}
      </div>
    </div>
  );
}
