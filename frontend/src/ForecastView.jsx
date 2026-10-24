import { useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "./api.js";
import { downloadCsv, fmtDay, fmtGWAxis, fmtInstant, fmtMW, niceAxis } from "./format.js";

function Tip({ active, payload, showActual }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="tip">
      <strong>{p.local}</strong>
      <div><i className="sw fc" /> Forecast {fmtMW(p.forecast_mw)}</div>
      {p.band_lo_mw != null && <div className="muted">Likely range {fmtMW(p.band_lo_mw)} – {fmtMW(p.band_hi_mw)}</div>}
      {showActual && p.actual_mw != null && (
        <>
          <div><i className="sw ac" /> Actual {fmtMW(p.actual_mw)}</div>
          <div className="muted">Error {fmtMW(p.error_mw, { sign: true })}</div>
        </>
      )}
    </div>
  );
}

export default function ForecastView({ day, cutoff }) {
  const { data, error, loading } = useApi("/api/forecast", { day, cutoff });
  const [showActual, setShowActual] = useState(true);

  const rows = useMemo(
    () => (data?.slots ?? []).map((s) => ({ ...s, band_range: s.band_lo_mw != null ? s.band_hi_mw - s.band_lo_mw : null })),
    [data],
  );

  const yAxis = useMemo(() => niceAxis(rows.flatMap((r) => [r.forecast_mw, r.actual_mw, r.band_hi_mw])), [rows]);

  if (error) return <div className="banner err" role="alert">{error.message}</div>;
  if (!data) return <p className="state">Loading forecast…</p>;

  const s = data.summary;
  const band = s.band;
  const hasActual = rows.some((r) => r.actual_mw != null);

  return (
    <section aria-busy={loading} className={loading ? "dim" : ""}>
      <p className="lede">
        Using the latest forecast published by <strong>{fmtInstant(data.cutoff_utc)}</strong>, wind should deliver about{" "}
        <strong>{s.forecast_gwh} GWh</strong> on <strong>{fmtDay(day)}</strong>, peaking near{" "}
        <strong>{fmtMW(s.peak_mw)}</strong> at {s.peak_at}.
        {band && (
          <>
            {" "}On {band.basis === "previous days" ? `the ${band.days} days before` : "other days in this period"}, actual output
            landed between <strong>{fmtMW(band.lo_mw, { sign: true })}</strong> and <strong>{fmtMW(band.hi_mw, { sign: true })}</strong> of
            the forecast 9 times out of 10 — the shaded band below.
          </>
        )}
      </p>

      <div className="panel">
        <div className="panel-head">
          <div className="legend">
            <span><i className="sw fc" /> Forecast at decision time</span>
            {band && <span><i className="sw bd" /> Likely range</span>}
            {hasActual && showActual && <span><i className="sw ac" /> What actually happened</span>}
          </div>
          {hasActual && (
            <label className="check">
              <input type="checkbox" checked={showActual} onChange={(e) => setShowActual(e.target.checked)} />
              Compare with actual
            </label>
          )}
        </div>
        <div className="chart" role="img" aria-label={`Half-hourly wind forecast for ${fmtDay(day)}`}>
          <ResponsiveContainer width="100%" height={340}>
            <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="local" interval={3} tick={{ fontSize: 12 }} tickLine={false} stroke="var(--line)" />
              <YAxis {...yAxis} tickFormatter={fmtGWAxis} tick={{ fontSize: 12 }} tickLine={false} axisLine={false} width={44}
                     label={{ value: "GW", angle: -90, position: "insideLeft", offset: 14, fontSize: 12, fill: "var(--muted)" }} />
              <Tooltip content={<Tip showActual={showActual} />} />
              <Area dataKey="band_lo_mw" stackId="b" stroke="none" fill="none" isAnimationActive={false} legendType="none" />
              <Area dataKey="band_range" stackId="b" stroke="none" fill="var(--forecast)" fillOpacity={0.14} isAnimationActive={false} legendType="none" />
              <Line dataKey="forecast_mw" stroke="var(--forecast)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
              {hasActual && showActual && (
                <Line dataKey="actual_mw" stroke="var(--actual)" strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <dl className="facts">
        <div><dt>Forecast published</dt><dd>{fmtInstant(s.published_min)}{s.published_min !== s.published_max && ` to ${fmtInstant(s.published_max)}`}</dd></div>
        <div><dt>Lowest point</dt><dd>{fmtMW(s.min_mw)} at {s.min_at}</dd></div>
        <div><dt>Peak</dt><dd>{fmtMW(s.peak_mw)} at {s.peak_at}</dd></div>
        {s.actual_gwh != null && (
          <div><dt>Actual energy</dt><dd>{s.actual_gwh} GWh vs {s.forecast_gwh_matched} GWh forecast</dd></div>
        )}
        {s.missing_slots > 0 && <div><dt>Missing slots</dt><dd>{s.missing_slots} half-hours had no forecast</dd></div>}
      </dl>

      <details className="table-wrap">
        <summary>Half-hourly values</summary>
        <div className="actions">
          <button className="btn" onClick={() => downloadCsv(`windward_${day}_cutoff${cutoff.replace(":", "")}.csv`,
            rows.map(({ band_range, ...r }) => r))}>Download CSV</button>
        </div>
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Time</th><th>Forecast</th><th>Range</th><th>Published</th><th>Actual</th><th>Error</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.start}>
                  <td>{r.local}</td>
                  <td>{fmtMW(r.forecast_mw)}</td>
                  <td>{r.band_lo_mw != null ? `${fmtMW(r.band_lo_mw)} – ${fmtMW(r.band_hi_mw)}` : "–"}</td>
                  <td>{fmtInstant(r.published)}</td>
                  <td>{fmtMW(r.actual_mw)}</td>
                  <td className={r.error_mw > 0 ? "over" : "under"}>{fmtMW(r.error_mw, { sign: true })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
