const TZ = "Europe/London";

export const fmtMW = (mw, { sign = false, digits = 1 } = {}) => {
  if (mw == null) return "–";
  const s = sign && mw > 0 ? "+" : mw < 0 ? "\u2212" : "";
  const a = Math.abs(mw);
  return a >= 1000 ? `${s}${(a / 1000).toFixed(digits)} GW` : `${s}${Math.round(a)} MW`;
};

const dayFmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
/** "2026-01-14" -> "Wed 14 Jan" (date-only strings are treated as plain calendar dates) */
export const fmtDay = (iso) => dayFmt.format(new Date(`${iso}T12:00:00Z`));

const dtFmt = new Intl.DateTimeFormat("en-GB", {
  weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: TZ,
});
/** UTC ISO instant -> UK local "Tue 13 Jan, 09:00" */
export const fmtInstant = (iso) => (iso ? dtFmt.format(new Date(iso)).replace(",", "") : "–");

export const fmtHHMM = (iso) =>
  new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: TZ }).format(new Date(iso));

export function downloadCsv(filename, rows) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const body = rows.map((r) => cols.map((c) => r[c] ?? "").join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([`${cols.join(",")}\n${body}\n`], { type: "text/csv" }));
  Object.assign(document.createElement("a"), { href: url, download: filename }).click();
  URL.revokeObjectURL(url);
}

/** Round axis bounds/ticks (e.g. 0, 2, 4, 6 GW) instead of Recharts' arbitrary ones. */
export function niceAxis(values, includeZero = true) {
  const v = values.filter((x) => x != null && Number.isFinite(x));
  let lo = Math.min(...v, includeZero ? 0 : Infinity);
  let hi = Math.max(...v, includeZero ? 0 : -Infinity);
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi === lo) return { domain: [0, 1000], ticks: [0, 500, 1000] };
  const raw = (hi - lo) / 5;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const start = Math.floor(lo / step) * step;
  const end = Math.ceil(hi / step) * step;
  const ticks = [];
  for (let t = start; t <= end + 1e-9; t += step) ticks.push(Math.round(t));
  return { domain: [start, end], ticks };
}
export const fmtGWAxis = (v) => String(Number((v / 1000).toFixed(2)));
