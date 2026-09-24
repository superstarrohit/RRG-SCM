// Inline-SVG charts: Donut, vertical glow bars, glow line chart, status bars, meter.
import React from "react";

// Tracks a wrapper element's rendered width so a chart's SVG viewBox can
// match its real pixel width exactly. Without this, viewBox stayed at a
// fixed design width while CSS stretched the SVG to fill wider panels —
// since height followed via the preserved aspect ratio, a chart in a wide
// panel rendered far taller than its intended height (and than neighboring
// cards), which is what made charts look oversized relative to everything
// else on the page.
function useMeasuredWidth(fallback) {
  const ref = React.useRef(null);
  const [width, setWidth] = React.useState(fallback);
  React.useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

// ---- Horizontal scroll slider ----
// Charts whose content can outgrow their panel (many bars, a long date
// range, more buyers than fit) already scroll horizontally via CSS overflow
// on their wrapper, but a thin native scrollbar is easy to miss and awkward
// to grab precisely. This tracks that wrapper's scroll position/size and
// exposes an explicit slider so growth in the underlying data (more months,
// more categories) stays navigable rather than just "scrollable if you find
// the edge". `ref` must point at the element with `overflow-x: auto` whose
// child is the oversized content (the chart's own wrapRef).
function useHScroll(ref) {
  const [state, setState] = React.useState({ show: false, value: 0, max: 0 });
  React.useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const update = () => {
      const max = Math.max(0, el.scrollWidth - el.clientWidth);
      // >20px, not >0 — .table-wrap's own -4px margin/4px padding trick
      // alone creates a few px of "overflow" that isn't real scrollable
      // content, so a small threshold avoids showing the slider for that.
      setState({ show: max > 20, value: Math.min(el.scrollLeft, max), max });
    };
    update();
    el.addEventListener("scroll", update, { passive: true });
    let ro;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(update);
      ro.observe(el);
      if (el.firstElementChild) ro.observe(el.firstElementChild);
    }
    return () => { el.removeEventListener("scroll", update); ro?.disconnect(); };
  }, [ref]);
  return state;
}

function HScrollSlider({ scrollRef }) {
  const { show, value, max } = useHScroll(scrollRef);
  if (!show) return null;
  return (
    <input
      type="range" className="chart-scrub" min={0} max={max} value={value}
      onChange={(e) => { if (scrollRef.current) scrollRef.current.scrollLeft = Number(e.target.value); }}
      aria-label="Scroll chart horizontally"
    />
  );
}

// CSS-variable references, not static hex — SVG presentation attributes
// (fill/stroke/stop-color) resolve var() same as any CSS property, so chart
// colors follow the active [data-accent] theme automatically.
export const PALETTE = {
  purple: "var(--primary)",
  blue: "var(--blue)",
  cyan: "var(--cyan)",
  green: "var(--green)",
  amber: "var(--amber)",
  red: "var(--red)",
  grey: "var(--muted)",
};

// ---- Pseudo-3D donut ----
// Tilts the ring into an ellipse and extrudes it downward (stacked darker
// copies of each arc) for a 3D disc look. Colors are CSS vars, so the darker
// "side wall" is derived with color-mix() and follows the active theme.
export function Donut3D({ segments, size = 230, thickness = 40, depth = 22, centerLabel, centerValue }) {
  const segs = (segments || []).filter((s) => (s.value || 0) > 0);
  const total = segs.reduce((s, x) => s + (x.value || 0), 0) || 1;
  const r = (size - thickness) / 2 - 6;
  const c = 2 * Math.PI * r;
  const cx = size / 2;
  const tilt = 0.56;                       // ellipse squash → perspective
  const H = size * tilt + depth + 16;      // svg height incl. extrusion

  // One flat ring of arcs at a given y-offset and color transform.
  const ring = (yOff, colorFn, key) => {
    let offset = 0;
    return segs.map((s, i) => {
      const len = ((s.value || 0) / total) * c;
      const el = (
        <circle
          key={`${key}-${i}`} cx={cx} cy={cx} r={r} fill="none"
          stroke={colorFn(s.color)} strokeWidth={thickness}
          strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset}
          transform={`rotate(-90 ${cx} ${cx})`} strokeLinecap="butt"
          style={{ transform: `translateY(${yOff}px)` }}
        />
      );
      offset += len;
      return el;
    });
  };

  const wall = (color) => `color-mix(in srgb, ${color} 55%, black)`;
  const depthLayers = [];
  for (let d = depth; d >= 1; d--) depthLayers.push(ring(d, wall, `d${d}`));

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 22, flexWrap: "wrap" }}>
      <svg viewBox={`0 0 ${size} ${H}`} style={{ width: size, height: H, flexShrink: 0, overflow: "visible" }}>
        <defs>
          <filter id="d3d-shadow" x="-30%" y="-30%" width="160%" height="180%">
            <feDropShadow dx="0" dy="6" stdDeviation="7" floodColor="rgba(0,0,0,0.45)" />
          </filter>
        </defs>
        <g transform={`translate(${cx} ${size / 2}) scale(1 ${tilt}) translate(${-cx} ${-size / 2})`}
           filter="url(#d3d-shadow)">
          {depthLayers}
          {ring(0, (col) => col, "top")}
        </g>
        {centerValue !== undefined && (
          <text x={cx} y={size / 2 * tilt + 2} textAnchor="middle" fontSize="17" fontWeight="800" fill="var(--text)">
            {centerValue}
          </text>
        )}
      </svg>
      <div className="legend" style={{ flexDirection: "column", gap: 8 }}>
        {segs.map((s, i) => (
          <div className="item" key={i}>
            <span className="swatch" style={{ background: s.color, borderRadius: "50%" }} />
            <span style={{ minWidth: 96 }}>{s.label}</span>
            <span className="mono" style={{ color: "var(--text)", fontWeight: 700 }}>
              {Math.round(((s.value || 0) / total) * 100)}%
            </span>
          </div>
        ))}
        {!segs.length && <div className="empty">No data.</div>}
      </div>
    </div>
  );
}

const MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// "2025-10" → "Oct 2025"; anything else passes through unchanged.
export function fmtMonthLabel(m) {
  const mm = /^(\d{4})-(\d{2})$/.exec(String(m || ""));
  return mm ? `${MONTH_ABBR[+mm[2] - 1]} ${mm[1]}` : m;
}

// ---- Ribbon chart ----
// A stacked-column series across a time axis, with each series' segments
// linked between adjacent periods by a curved (cubic-bezier) ribbon — the
// Power BI "ribbon chart" look. Within every period the biggest series sits
// on top; the ribbons show how each series' share flows month to month.
//   series: [{ name, values: number[] }]   (one value per month/period)
//   months: string[]                        (period labels, x-axis)
// `onPeriod(index)` + `clickable` turn each column into a drill target (Power
// BI-style click-to-drill); `showValues` labels each segment tall enough to
// hold its value, with an outlined fill so it reads on every segment color.
export function RibbonChart({ series, months, valueFormat = (v) => v, height = 300, colors,
                              onPeriod, clickable = false, showValues = true }) {
  const [wrapRef, measuredW] = useMeasuredWidth(760);
  const list = (series || []).filter((s) => (s.values || []).some((v) => (v || 0) > 0));
  const n = (months || []).length;
  if (!list.length || n < 2) return <div className="empty">Not enough history to draw a ribbon chart.</div>;

  const pal = colors && colors.length ? colors
    : [PALETTE.purple, PALETTE.blue, PALETTE.cyan, PALETTE.green, PALETTE.amber, PALETTE.red, "var(--primary-2)"];
  const colorOf = (i) => pal[i % pal.length];

  const minContentW = Math.max(560, n * 104);
  const W = Math.max(measuredW, minContentW);
  const padL = 56, padR = 16, padT = 16, padB = 34;
  const chartH = height - padT - padB;
  const chartW = W - padL - padR;
  const colGap = chartW / n;                 // slot width per period
  const barW = Math.min(58, colGap * 0.5);   // stacked-column width
  const cx = (i) => padL + colGap * i + colGap / 2;   // period center x

  // Column total per period → shared y-scale across all periods.
  const totals = months.map((_, i) => list.reduce((s, ser) => s + (ser.values[i] || 0), 0));
  const max = Math.max(1, ...totals);
  const yScale = (v) => (v / max) * chartH;

  // For each period, rank series by that period's value and stack them from
  // the baseline (0 axis) upward — an upright stacked column, largest on top.
  // Record each series' top/bottom pixel y so we can draw its column segment
  // and thread ribbons into neighbors.
  // segs[periodIndex][seriesIndex] = { y0, y1 } (top, bottom) or null.
  const baseY = padT + chartH;               // the 0 axis (bottom)
  const segs = months.map((_, i) => {
    const order = list.map((_, si) => si)
      .filter((si) => (list[si].values[i] || 0) > 0)
      .sort((a, b) => (list[a].values[i] || 0) - (list[b].values[i] || 0)); // smallest first
    const out = new Array(list.length).fill(null);
    let acc = 0;                              // stack upward from the baseline
    for (const si of order) {
      const h = yScale(list[si].values[i] || 0);
      const y1 = baseY - acc;                 // bottom of this segment
      out[si] = { y0: y1 - h, y1 };
      acc += h;
    }
    return out;
  });

  const ticks = 4;
  const gid = React.useId();

  // A cubic-bezier band connecting a series' right edge in period i to its
  // left edge in period i+1 (smooth S-curve between the two column stacks).
  const ribbonPath = (si, i) => {
    const a = segs[i][si], b = segs[i + 1][si];
    if (!a || !b) return null;
    const xR = cx(i) + barW / 2, xL = cx(i + 1) - barW / 2;
    const mx = (xR + xL) / 2;
    return `M ${xR} ${a.y0} C ${mx} ${a.y0}, ${mx} ${b.y0}, ${xL} ${b.y0} `
         + `L ${xL} ${b.y1} C ${mx} ${b.y1}, ${mx} ${a.y1}, ${xR} ${a.y1} Z`;
  };

  return (
    <div>
    <div className="chart table-wrap" ref={wrapRef}>
      <svg viewBox={`0 0 ${W} ${height}`} style={{ minWidth: minContentW, width: "100%", height }}>
        <defs>
          {list.map((_, si) => (
            <linearGradient key={si} id={`rb-${gid}-${si}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colorOf(si)} stopOpacity="0.98" />
              <stop offset="100%" stopColor={colorOf(si)} stopOpacity="0.62" />
            </linearGradient>
          ))}
        </defs>

        {/* horizontal gridlines + value axis */}
        {Array.from({ length: ticks + 1 }).map((_, i) => {
          const y = padT + (chartH * i) / ticks;
          const val = max * (1 - i / ticks);
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="var(--border)" strokeWidth="1" />
              <text x={padL - 8} y={y + 4} textAnchor="end" fontSize="10" fill="var(--muted)">
                {valueFormat(val)}
              </text>
            </g>
          );
        })}

        {/* ribbons behind the columns */}
        {months.slice(0, -1).map((_, i) =>
          list.map((_, si) => {
            const d = ribbonPath(si, i);
            return d ? (
              <path key={`${i}-${si}`} d={d} fill={colorOf(si)} opacity="0.28" />
            ) : null;
          })
        )}

        {/* stacked column segments, each tagged with its value when tall
            enough to hold the label (outlined text reads on any fill color) */}
        {months.map((_, i) =>
          list.map((ser, si) => {
            const s = segs[i][si];
            if (!s) return null;
            const segH = s.y1 - s.y0;
            return (
              <g key={`${i}-${si}`}>
                <rect x={cx(i) - barW / 2} y={s.y0}
                      width={barW} height={Math.max(segH, 1)} rx="4"
                      fill={`url(#rb-${gid}-${si})`} />
                {showValues && segH >= 18 && (
                  <text x={cx(i)} y={(s.y0 + s.y1) / 2 + 4} textAnchor="middle" fontSize="10.5"
                        fontWeight="700" fill="#fff"
                        style={{ paintOrder: "stroke", stroke: "rgba(0,0,0,0.55)", strokeWidth: 3, strokeLinejoin: "round" }}>
                    {valueFormat(ser.values[i])}
                  </text>
                )}
              </g>
            );
          })
        )}

        {/* full-height click targets, one per period column, for drilldown */}
        {clickable && onPeriod && months.map((_, i) => (
          <rect key={`hit-${i}`} x={cx(i) - colGap / 2} y={padT} width={colGap} height={chartH}
                fill="transparent" style={{ cursor: "pointer" }} onClick={() => onPeriod(i)} />
        ))}

        {/* period (x-axis) labels — YYYY-MM shown as "Mon YYYY" */}
        {months.map((m, i) => (
          <text key={i} x={cx(i)} y={height - padB + 18} textAnchor="middle"
                fontSize="10.5" fill="var(--text-dim)">{fmtMonthLabel(m)}</text>
        ))}
      </svg>
    </div>
    <HScrollSlider scrollRef={wrapRef} />

      <div className="legend" style={{ marginTop: 10, flexWrap: "wrap", gap: 12 }}>
        {list.map((s, si) => (
          <div className="item" key={si}>
            <span className="swatch" style={{ background: colorOf(si), borderRadius: 3 }} />
            <span>{s.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

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
export function VBars({ data, valueFormat = (v) => v, height = 240, color = PALETTE.purple, showValues = false }) {
  const [wrapRef, measuredW] = useMeasuredWidth(560);
  if (!data.length) return <div className="empty">No data.</div>;
  const max = Math.max(1, ...data.map((d) => d.value || 0));
  const minContentW = Math.max(360, data.length * 92);
  const W = Math.max(measuredW, minContentW);
  const padL = 44, padB = 34, padT = showValues ? 28 : 12;
  const chartH = height - padB - padT;
  const bw = Math.min(46, (W - padL) / data.length - 22);
  const gap = (W - padL) / data.length;
  const ticks = 4;
  const gid = React.useId();
  return (
    <div>
    <div className="chart table-wrap" ref={wrapRef}>
      <svg viewBox={`0 0 ${W} ${height}`} style={{ minWidth: minContentW, width: "100%", height }}>
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
              {showValues && (
                <text x={x + bw / 2} y={y - 8} textAnchor="middle" fontSize="11"
                      fontWeight="700" fill="var(--text)">{valueFormat(d.value)}</text>
              )}
              <text x={x + bw / 2} y={height - padB + 16} textAnchor="middle" fontSize="11" fill="var(--text-dim)">
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
    <HScrollSlider scrollRef={wrapRef} />
    </div>
  );
}

// ---- Clickable bar chart (drives the Power BI-style drilldown) ----
// Renders value-labelled bars; clicking a bar calls onBar(item) so the parent
// can drill into that period. `clickable` toggles the cursor/hover affordance.
export function DrillBars({ data, valueFormat = (v) => v, height = 300, color = PALETTE.cyan, onBar, clickable = true }) {
  const [wrapRef, measuredW] = useMeasuredWidth(720);
  if (!data.length) return <div className="empty">No data.</div>;
  const max = Math.max(1, ...data.map((d) => d.value || 0));
  const minContentW = Math.max(420, data.length * (data.length > 20 ? 40 : 74));
  const W = Math.max(measuredW, minContentW);
  const padL = 56, padB = 40, padT = 22;
  const chartH = height - padB - padT;
  const gap = (W - padL) / data.length;
  const bw = Math.min(56, gap - (data.length > 20 ? 8 : 20));
  const ticks = 4;
  const gid = React.useId();
  const many = data.length > 16;
  return (
    <div>
    <div className="chart table-wrap" ref={wrapRef}>
      <svg viewBox={`0 0 ${W} ${height}`} style={{ minWidth: minContentW, width: "100%", height }}>
        <defs>
          <linearGradient id={`db-${gid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.98" />
            <stop offset="100%" stopColor={color} stopOpacity="0.40" />
          </linearGradient>
          <filter id={`dbg-${gid}`} x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="3.5" result="b" />
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
                {valueFormat(val)}
              </text>
            </g>
          );
        })}
        {data.map((d, i) => {
          const h = ((d.value || 0) / max) * chartH;
          const x = padL + gap * i + (gap - bw) / 2;
          const y = padT + chartH - h;
          const step = Math.max(1, Math.ceil(data.length / 16));
          const showLabel = !many || i % step === 0 || i === data.length - 1;
          return (
            <g key={i} onClick={onBar ? () => onBar(d) : undefined}
               style={{ cursor: clickable && onBar ? "pointer" : "default" }}>
              {/* full-height hit area so the whole column is clickable */}
              <rect x={padL + gap * i} y={padT} width={gap} height={chartH} fill="transparent" />
              <rect x={x} y={y} width={Math.max(bw, 2)} height={Math.max(h, 1)} rx="6"
                    fill={`url(#db-${gid})`} filter={`url(#dbg-${gid})`} />
              <text x={x + bw / 2} y={y - 6} textAnchor="middle" fontSize="10.5"
                    fontWeight="700" fill="var(--text)">{valueFormat(d.value)}</text>
              {showLabel && (
                <text x={padL + gap * i + gap / 2} y={height - padB + 16} textAnchor="middle"
                      fontSize="10.5" fill="var(--text-dim)">{d.label}</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
    <HScrollSlider scrollRef={wrapRef} />
    </div>
  );
}

// ---- Line chart with glow + area ----
export function LineChart({ data, valueFormat = (v) => v, height = 260, color = PALETTE.cyan }) {
  const [wrapRef, measuredW] = useMeasuredWidth(720);
  if (data.length < 2) return <div className="empty">Not enough points.</div>;
  const max = Math.max(1, ...data.map((d) => d.value || 0));
  const minContentW = 560;
  const W = Math.max(measuredW, minContentW);
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
    <div className="chart table-wrap" ref={wrapRef}>
      <svg viewBox={`0 0 ${W} ${height}`} style={{ minWidth: minContentW, width: "100%", height }}>
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
        {/* With many points (e.g. daily), thin the dots and x-labels so the
            axis stays legible — always keep the first and last. */}
        {data.map((d, i) => {
          const showDot = data.length <= 60;
          const step = Math.max(1, Math.ceil(data.length / 14));
          const showLabel = i % step === 0 || i === data.length - 1;
          return (
            <g key={i}>
              {showDot && <circle cx={x(i)} cy={y(d.value)} r="4" fill={color} filter={`url(#lg-${gid})`} />}
              {showLabel && (
                <text x={x(i)} y={height - padB + 16} textAnchor="middle" fontSize="10.5" fill="var(--text-dim)">
                  {d.label}
                </text>
              )}
            </g>
          );
        })}
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
