const WIDTH = 120;
const HEIGHT = 28;

/** One series on a fixed 0..max scale, so neighbouring cards are comparable. */
export function Sparkline({
  values,
  max,
  label,
}: {
  values: (number | null)[];
  max: number;
  label: string;
}) {
  const points = values
    .map((value, index) => {
      if (value == null || max <= 0) return null;
      const x = values.length > 1 ? (index / (values.length - 1)) * WIDTH : WIDTH;
      const y = HEIGHT - 1 - (Math.min(value, max) / max) * (HEIGHT - 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
  return (
    <svg
      aria-label={label}
      className="h-7 w-full text-primary"
      preserveAspectRatio="none"
      role="img"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
    >
      <title>{label}</title>
      <line
        stroke="rgb(var(--zinc-800))"
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
        x1="0"
        x2={WIDTH}
        y1={HEIGHT - 0.5}
        y2={HEIGHT - 0.5}
      />
      <polyline
        fill="none"
        points={points}
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
