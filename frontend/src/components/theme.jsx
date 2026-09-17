// Theming: a light/dark mode toggle plus a "Theme Center" of 25+ curated
// accent palettes. Each palette is exactly 7 core colors (primary,
// secondary, cyan/accent, green, amber, blue, red); every gradient, glow,
// badge tint and focus ring in index.css derives from those 7 via
// color-mix(), so picking a palette re-themes the whole app consistently.
// Keep this list in sync with the [data-accent] blocks in index.css.
import React from "react";
import Icon from "./icons.jsx";

export const THEMES = [
  { key: "violet", label: "Violet Dream", colors: ["#7c5cff", "#4d7cff", "#22d3ee", "#34d399", "#fbbf24", "#60a5fa", "#fb7185"] },
  { key: "ocean", label: "Ocean Blue", colors: ["#2563eb", "#0ea5e9", "#06b6d4", "#10b981", "#f59e0b", "#3b82f6", "#ef4444"] },
  { key: "indigo", label: "Midnight Indigo", colors: ["#4338ca", "#4f46e5", "#22d3ee", "#22c55e", "#eab308", "#6366f1", "#f43f5e"] },
  { key: "emerald", label: "Emerald Forest", colors: ["#059669", "#10b981", "#14b8a6", "#22c55e", "#d97706", "#0284c7", "#dc2626"] },
  { key: "sunset", label: "Sunset Coral", colors: ["#fb7185", "#f97316", "#06b6d4", "#22c55e", "#f59e0b", "#38bdf8", "#e11d48"] },
  { key: "royal", label: "Royal Purple", colors: ["#9333ea", "#a855f7", "#22d3ee", "#16a34a", "#eab308", "#6366f1", "#db2777"] },
  { key: "crimson", label: "Crimson Ember", colors: ["#dc2626", "#f97316", "#0ea5e9", "#16a34a", "#f59e0b", "#3b82f6", "#b91c1c"] },
  { key: "teal", label: "Teal Wave", colors: ["#0d9488", "#14b8a6", "#22d3ee", "#22c55e", "#eab308", "#0ea5e9", "#f43f5e"] },
  { key: "rosegold", label: "Rose Gold", colors: ["#e11d48", "#f43f5e", "#f59e0b", "#10b981", "#fbbf24", "#60a5fa", "#be123c"] },
  { key: "slate", label: "Slate Steel", colors: ["#475569", "#64748b", "#38bdf8", "#22c55e", "#eab308", "#3b82f6", "#ef4444"] },
  { key: "amber", label: "Amber Gold", colors: ["#d97706", "#f59e0b", "#06b6d4", "#16a34a", "#fbbf24", "#2563eb", "#dc2626"] },
  { key: "lavender", label: "Lavender Mist", colors: ["#a78bfa", "#c4b5fd", "#67e8f9", "#6ee7b7", "#fde68a", "#93c5fd", "#fda4af"] },
  { key: "cobalt", label: "Cobalt Frost", colors: ["#1d4ed8", "#2563eb", "#38bdf8", "#22c55e", "#eab308", "#60a5fa", "#f43f5e"] },
  { key: "berry", label: "Berry Punch", colors: ["#be185d", "#db2777", "#22d3ee", "#22c55e", "#f59e0b", "#6366f1", "#9f1239"] },
  { key: "lime", label: "Lime Zest", colors: ["#65a30d", "#84cc16", "#22d3ee", "#16a34a", "#eab308", "#3b82f6", "#ef4444"] },
  { key: "graphite", label: "Graphite Neon", colors: ["#52525b", "#71717a", "#22d3ee", "#34d399", "#facc15", "#38bdf8", "#fb7185"] },
  { key: "ruby", label: "Ruby Night", colors: ["#9f1239", "#e11d48", "#0ea5e9", "#16a34a", "#f59e0b", "#3b82f6", "#be123c"] },
  { key: "copper", label: "Copper Bronze", colors: ["#b45309", "#d97706", "#0891b2", "#15803d", "#f59e0b", "#2563eb", "#b91c1c"] },
  { key: "sky", label: "Sky Breeze", colors: ["#0284c7", "#0ea5e9", "#22d3ee", "#22c55e", "#eab308", "#38bdf8", "#f87171"] },
  { key: "mint", label: "Mint Fresh", colors: ["#10b981", "#34d399", "#22d3ee", "#4ade80", "#fbbf24", "#60a5fa", "#fb7185"] },
  { key: "magenta", label: "Magenta Pulse", colors: ["#c026d3", "#d946ef", "#22d3ee", "#22c55e", "#eab308", "#6366f1", "#f43f5e"] },
  { key: "sapphire", label: "Sapphire", colors: ["#1e40af", "#3b82f6", "#0ea5e9", "#16a34a", "#eab308", "#60a5fa", "#dc2626"] },
  { key: "autumn", label: "Autumn Blaze", colors: ["#ea580c", "#f97316", "#0891b2", "#65a30d", "#f59e0b", "#2563eb", "#dc2626"] },
  { key: "turquoise", label: "Turquoise Tide", colors: ["#0d9488", "#06b6d4", "#22d3ee", "#22c55e", "#eab308", "#3b82f6", "#f43f5e"] },
  { key: "plum", label: "Plum Velvet", colors: ["#6d28d9", "#7c3aed", "#22d3ee", "#22c55e", "#f59e0b", "#6366f1", "#db2777"] },
  { key: "steelcyan", label: "Steel Cyan", colors: ["#0e7490", "#0891b2", "#22d3ee", "#22c55e", "#eab308", "#3b82f6", "#f43f5e"] },
  { key: "goldenhour", label: "Golden Hour", colors: ["#f59e0b", "#fbbf24", "#22d3ee", "#22c55e", "#facc15", "#60a5fa", "#ef4444"] },
  { key: "cherry", label: "Cherry Blossom", colors: ["#ec4899", "#f472b6", "#22d3ee", "#34d399", "#fbbf24", "#60a5fa", "#f43f5e"] },
  { key: "deepocean", label: "Deep Ocean", colors: ["#0c4a6e", "#075985", "#0ea5e9", "#059669", "#d97706", "#0284c7", "#b91c1c"] },
  { key: "neon", label: "Neon Cyberpunk", colors: ["#d946ef", "#7c3aed", "#22d3ee", "#22c55e", "#facc15", "#3b82f6", "#f43f5e"] },
];

const ThemeContext = React.createContext(null);

const load = (k, d) => { try { return localStorage.getItem(k) || d; } catch { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } };

function systemPrefersDark() {
  try { return window.matchMedia("(prefers-color-scheme: dark)").matches; } catch { return true; }
}

export function ThemeProvider({ children }) {
  const [mode, setMode] = React.useState(() => load("scm.theme.mode", "dark")); // "dark" | "light" | "system"
  const [accent, setAccent] = React.useState(() => load("scm.theme.accent", "violet"));
  const [systemDark, setSystemDark] = React.useState(systemPrefersDark);

  React.useEffect(() => {
    let mq;
    try { mq = window.matchMedia("(prefers-color-scheme: dark)"); } catch { return undefined; }
    const onChange = (e) => setSystemDark(e.matches);
    if (mq.addEventListener) mq.addEventListener("change", onChange);
    else mq.addListener(onChange);
    return () => (mq.removeEventListener ? mq.removeEventListener("change", onChange) : mq.removeListener(onChange));
  }, []);

  const effectiveMode = mode === "system" ? (systemDark ? "dark" : "light") : mode;

  React.useEffect(() => { document.documentElement.setAttribute("data-theme", effectiveMode); }, [effectiveMode]);
  React.useEffect(() => { document.documentElement.setAttribute("data-accent", accent); }, [accent]);
  React.useEffect(() => save("scm.theme.mode", mode), [mode]);
  React.useEffect(() => save("scm.theme.accent", accent), [accent]);

  const value = { mode, setMode, accent, setAccent, effectiveMode, themes: THEMES };
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return React.useContext(ThemeContext);
}

export function ThemeCenterButton() {
  const [open, setOpen] = React.useState(false);
  return (
    <>
      <button className="btn ghost" onClick={() => setOpen(true)} title="Theme Center">
        <Icon name="palette" />
        <span className="btn-label">Theme</span>
      </button>
      {open && <ThemeCenter onClose={() => setOpen(false)} />}
    </>
  );
}

function ThemeCenter({ onClose }) {
  const t = useTheme();
  React.useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  if (!t) return null;

  return (
    <div className="tc-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="tc-panel" role="dialog" aria-modal="true" aria-label="Theme Center">
        <div className="tc-head">
          <div className="tc-title"><Icon name="palette" /> Theme Center</div>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button>
        </div>

        <div className="tc-section">
          <div className="tc-section-label">Appearance</div>
          <div className="seg" style={{ marginBottom: 0 }}>
            <button className={t.mode === "light" ? "on" : ""} onClick={() => t.setMode("light")}>
              <Icon name="sun" /> Light
            </button>
            <button className={t.mode === "dark" ? "on" : ""} onClick={() => t.setMode("dark")}>
              <Icon name="moon" /> Dark
            </button>
            <button className={t.mode === "system" ? "on" : ""} onClick={() => t.setMode("system")}>
              <Icon name="auto" /> Auto
            </button>
          </div>
        </div>

        <div className="tc-section">
          <div className="tc-section-label">
            Color theme <span className="tc-count">{THEMES.length} available</span>
          </div>
          <div className="tc-grid">
            {THEMES.map((th) => (
              <button
                key={th.key}
                className={`tc-swatch${t.accent === th.key ? " on" : ""}`}
                onClick={() => t.setAccent(th.key)}
                title={th.label}
              >
                <span className="tc-dots">
                  {th.colors.map((c, i) => <span key={i} className="tc-dot" style={{ background: c }} />)}
                </span>
                <span className="tc-swatch-label">{th.label}</span>
                {t.accent === th.key && <span className="tc-check"><Icon name="check" /></span>}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
