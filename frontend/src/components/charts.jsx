// Inline-SVG charts: Donut, vertical glow bars, glow line chart, status bars, meter.
import React from "react";

export const PALETTE = {
  purple: "#8b7bff",
  blue: "#60a5fa",
  cyan: "#22d3ee",
  green: "#34d399",
  amber: "#fbbf24",
  red: "#fb7185",
  grey: "#64748b",
};

// ---- Donut chart ----
export function Donut({ segments, size = 168, thickness = 26, centerLabel, centerValue }) {
  const total = segments.reduce((s, x) => s + (x.value || 0), 0) || 1;
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const cx = size / 2;
  let offset = 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
      <svg viewBox={`0 0 ${size} ${size}`} style={{ width: size, height: size, flexShrink: 0 }}>
        <circle cx={cx} cy={cx} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={thickness} />
        {segments.map((s, i) => {
          const frac = (s.value || 0) / total;
          const len = frac * c;
          const el = (
            <circle
              key={i} cx={cx} cy={cx} r={r} fill="none"
              stroke={s.color} strokeWidth={thickness}
              strokeDasharray={`${len} ${c - len}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${cx} ${cx})`}
              strokeLinecap="butt"
            />
          );
          offset += len;
          return el;
        })}
        {(centerValue !== undefined) && (
          <>
            <text x={cx} y={cx - 4} textAnchor="middle" fontSize="24" fontWeight="800" fill="var(--text)">{centerValue}</text>
            <text x={cx} y={cx + 16} textAnchor="middle" fontSize="11" fill="var(--muted)">{centerLabel}</text>
          </>
        )}
      </svg>
      <div className="legend" style={{ flexDirection: "column", gap: 8 }}>
        {segments.map((s, i) => (
          <div className="item" key={i}>
            <span className="swatch" style={{ background: s.color, borderRadius: "50%" }} />
            <span style={{ minWidth: 90 }}>{s.label}</span>
            <span className="mono" style={{ color: "var(--text)", fontWeight: 700 }}>
              {Math.round(((s.value || 0) / total) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Vertical bar chart with glow ----
export function VBars({ data, valueFormat = (v) => v, height = 240, color = PALETTE.purple }) {
  if (!data.length) return <div className="empty">No data.</div>;
  const max = Math.max(1, ...data.map((d) => d.value || 0));
  const W = Math.max(360, data.length * 92);
  const padL = 44, padB = 34, padT = 12;
  const chartH = height - padB - padT;
  const bw = Math.min(46, (W - padL) / data.length - 22);
  const gap = (W - padL) / data.length;
  const ticks = 4;
  const gid = React.useId();
  return (
    <div className="chart table-wrap">
      <svg viewBox={`0 0 ${W} ${height}`} style={{ minWidth: W }}>
        <defs>
          <linearGradient id={`vb-${gid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.95" />
            <stop offset="100%" stopColor={color} stopOpacity="0.35" />
          </linearGradient>
          <filter id={`glow-${gid}`} x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="4" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        {Array.from({ length: ticks + 1 }).map((_, i) => {
          const y = padT + (chartH * i) / ticks;
          const val = max * (1 - i / ticks);
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={W} y2={y} stroke="var(--border)" strokeWidth="1" />
              <text x={padL - 8} y={y + 4} textAnchor="end" fontSize="10" fill="var(--muted)">
                {valueFormat(Math.round(val))}
              </text>
            </g>
          );
        })}
        {data.map((d, i) => {
          const h = ((d.value || 0) / max) * chartH;
          const x = padL + gap * i + (gap - bw) / 2;
          const y = padT + chartH - h;
          return (
            <g key={i}>
              <rect x={x} y={y} width={bw} height={Math.max(h, 1)} rx="7"
                    fill={`url(#vb-${gid})`} filter={`url(#glow-${gid})`} />
              <text x={x + bw / 2} y={height - padB + 16} textAnchor="middle" fontSize="11" fill="var(--text-dim)">
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ---- Line chart with glow + area ----
export function LineChart({ data, valueFormat = (v) => v, height = 260, color = PALETTE.cyan }) {
  if (data.length < 2) return <div className="empty">Not enough points.</div>;
  const max = Math.max(1, ...data.map((d) => d.value || 0));
  const W = 720;
  const padL = 52, padB = 34, padT = 14, padR = 14;
  const chartH = height - padB - padT;
  const chartW = W - padL - padR;
  const x = (i) => padL + (chartW * i) / (data.length - 1);
  const y = (v) => padT + chartH - ((v || 0) / max) * chartH;
  const pts = data.map((d, i) => `${x(i)},${y(d.value)}`).join(" ");
  const area = `${padL},${padT + chartH} ${pts} ${x(data.length - 1)},${padT + chartH}`;
  const ticks = 4;
  const gid = React.useId();
  return (
    <div className="chart table-wrap">
      <svg viewBox={`0 0 ${W} ${height}`} style={{ minWidth: 560 }}>
        <defs>
          <linearGradient id={`la-${gid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
          <filter id={`lg-${gid}`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        {Array.from({ length: ticks + 1 }).map((_, i) => {
          const yy = padT + (chartH * i) / ticks;
          const val = max * (1 - i / ticks);
          return (
            <g key={i}>
              <line x1={padL} y1={yy} x2={W - padR} y2={yy} stroke="var(--border)" strokeWidth="1" />
              <text x={padL - 8} y={yy + 4} textAnchor="end" fontSize="10" fill="var(--muted)">
                {valueFormat(Math.round(val))}
              </text>
            </g>
          );
        })}
        <polygon points={area} fill={`url(#la-${gid})`} />
        <polyline points={pts} fill="none" stroke={color} strokeWidth="3"
                  strokeLinejoin="round" strokeLinecap="round" filter={`url(#lg-${gid})`} />
        {data.map((d, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(d.value)} r="4" fill={color} filter={`url(#lg-${gid})`} />
            <text x={x(i)} y={height - padB + 16} textAnchor="middle" fontSize="10.5" fill="var(--text-dim)">
              {d.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

// ---- Status distribution bars (label + inline fill + value) ----
export function StatusBars({ rows, valueFormat = (v) => v }) {
  if (!rows.length) return <div className="empty">No data.</div>;
  const max = Math.max(1, ...rows.map((r) => r.value || 0));
  return (
    <div className="hbar-list">
      {rows.map((r, i) => (
        <div className="hbar" key={i}>
          <div className="hbar-fill" style={{ width: `${((r.value || 0) / max) * 100}%`, background: r.color }} />
          <div className="hbar-left">
            <span className="hbar-dot" style={{ background: r.color }} />
            <span>{r.label}</span>
          </div>
          <span className="hbar-val">{valueFormat(r.value)}</span>
        </div>
      ))}
    </div>
  );
}

// ---- Meter card ----
export function Meter({ label, value, pct, color = PALETTE.green }) {
  return (
    <div className="panel" style={{ marginBottom: 0 }}>
      <div className="label" style={{ color: "var(--muted)", fontSize: 12, fontWeight: 600 }}>{label}</div>
      <div className="value" style={{ fontSize: 26, fontWeight: 800, marginTop: 4 }}>{value}</div>
      <div className="meter-track">
        <div className="meter-fill" style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: color }} />
      </div>
    </div>
  );
}
