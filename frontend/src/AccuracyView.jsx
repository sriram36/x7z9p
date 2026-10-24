import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "./api.js";
import { fmtDay, fmtGWAxis, fmtMW, niceAxis } from "./format.js";
const axis = { tick: { fontSize: 12 }, tickLine: false, stroke: "var(--line)" };
const mwTip = (v) => fmtMW(v, { sign: false });

function Chart({ title, note, children }) {
  return (
    <figure className="panel">
      <figcaption>
        <h3>{title}</h3>
        {note && <p>{note}</p>}
      </figcaption>
      <div className="chart">{children}</div>
    </figure>
  );
}

export default function AccuracyView({ days, cutoff }) {
  const [from, setFrom] = useState(days[0]);
  const [to, setTo] = useState(days[days.length - 1]);
  const params = { start: from, end: to, cutoff };
  const acc = useApi("/api/accuracy", params);
  const hor = useApi("/api/horizon", params);

  const picker = (
    <div className="range" role="group" aria-label="Period">
      <label>From
        <select value={from} onChange={(e) => { setFrom(e.target.value); if (e.target.value > to) setTo(e.target.value); }}>
          {days.map((d) => <option key={d} value={d}>{fmtDay(d)}</option>)}
        </select>
      </label>
      <label>To
        <select value={to} onChange={(e) => { setTo(e.target.value); if (e.target.value < from) setFrom(e.target.value); }}>
          {days.map((d) => <option key={d} value={d}>{fmtDay(d)}</option>)}
        </select>
      </label>
    </div>
  );

  if (acc.error) return <div className="banner err" role="alert">{acc.error.message}</div>;
  if (!acc.data) return <p className="state">Loading accuracy…</p>;

  const o = acc.data.overall;
  const axDay = niceAxis(acc.data.by_day.flatMap((d) => [d.mae_mw, d.bias_mw]));
  const axHour = niceAxis(acc.data.by_hour.map((d) => d.bias_mw));
  const axHor = niceAxis((hor.data?.buckets ?? []).map((d) => d.mae_mw));
  const h = hor.data;

  return (
    <section aria-busy={acc.loading} className={acc.loading ? "dim" : ""}>
      {picker}
      <p className="lede">
        Across <strong>{acc.data.period.days} delivery days</strong>, the forecast available at {cutoff} the day before was off by{" "}
        <strong>{fmtMW(o.mae_mw)}</strong> on average ({o.nmae_pct}% of average output). It was too high in{" "}
        <strong>{o.over_share_pct}%</strong> of half-hours, and in 1 half-hour in 20 it was too high by more than{" "}
        <strong>{fmtMW(o.p95_over_mw)}</strong> — that is the shortfall worth planning for.
      </p>

      <dl className="facts metrics">
        <div><dt>Mean absolute error</dt><dd>{fmtMW(o.mae_mw)}</dd><small>Typical size of a miss, in either direction</small></div>
        <div><dt>Root mean square error</dt><dd>{fmtMW(o.rmse_mw)}</dd><small>Like the above but punishes big misses harder</small></div>
        <div><dt>Bias</dt><dd>{fmtMW(o.bias_mw, { sign: true })}</dd><small>Average of forecast − actual; above zero means too optimistic</small></div>
        <div><dt>90% of misses are under</dt><dd>{fmtMW(o.p90_abs_mw)}</dd><small>90th percentile of absolute error</small></div>
        <div><dt>Worst 1-in-20 over-forecast</dt><dd>{fmtMW(o.p95_over_mw)}</dd><small>Size of the shortfall you may need to buy back</small></div>
        <div><dt>Half-hours compared</dt><dd>{o.n.toLocaleString("en-GB")}</dd><small>Forecast and actual both available</small></div>
      </dl>

      <Chart title="Error by delivery day" note="Bars: average miss. Line: bias (above zero = forecast too high).">
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={acc.data.by_day} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="day" tickFormatter={(d) => d.slice(8)} interval={1} {...axis} />
            <YAxis {...axDay} tickFormatter={fmtGWAxis} width={44} tickLine={false} axisLine={false} tick={{ fontSize: 12 }}
                   label={{ value: "GW", angle: -90, position: "insideLeft", offset: 14, fontSize: 12, fill: "var(--muted)" }} />
            <Tooltip labelFormatter={fmtDay} formatter={(v, n) => [mwTip(v), n]} />
            <Bar dataKey="mae_mw" name="Average miss" fill="var(--forecast)" isAnimationActive={false} />
            <Line dataKey="bias_mw" name="Bias" stroke="var(--over)" strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </Chart>

      {h && (
        <Chart
          title="Error by how early the forecast was published"
          note={`Waiting pays: older forecasts are worse. Teal bars are the lead times a ${cutoff} decision actually uses (${h.decision_window_h?.[0]}–${h.decision_window_h?.[1]} h before delivery).`}
        >
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={h.buckets} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="label" {...axis} />
              <YAxis {...axHor} tickFormatter={fmtGWAxis} width={44} tickLine={false} axisLine={false} tick={{ fontSize: 12 }}
                     label={{ value: "GW", angle: -90, position: "insideLeft", offset: 14, fontSize: 12, fill: "var(--muted)" }} />
              <Tooltip formatter={(v) => [mwTip(v), "Average miss"]} labelFormatter={(l) => `Published ${l} before`} />
              <Bar dataKey="mae_mw" isAnimationActive={false}>
                {h.buckets.map((b) => <Cell key={b.label} fill={b.in_decision_window ? "var(--forecast)" : "var(--line-strong)"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Chart>
      )}

      <Chart title="Bias by time of day" note="Amber: forecast too high (shortfall risk). Blue: forecast too low.">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={acc.data.by_hour} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="hour" tickFormatter={(x) => `${String(x).padStart(2, "0")}:00`} interval={2} {...axis} />
            <YAxis {...axHour} tickFormatter={fmtGWAxis} width={44} tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
            <Tooltip labelFormatter={(x) => `${String(x).padStart(2, "0")}:00`} formatter={(v) => [fmtMW(v, { sign: true }), "Bias"]} />
            <Bar dataKey="bias_mw" isAnimationActive={false}>
              {acc.data.by_hour.map((b) => <Cell key={b.hour} fill={b.bias_mw > 0 ? "var(--over)" : "var(--under)"} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Chart>

      <figure className="panel">
        <figcaption>
          <h3>Error by wind level</h3>
          <p>Miss size depends on how hard the wind is blowing.</p>
        </figcaption>
        <div className="scroll">
          <table>
            <thead><tr><th>Actual output</th><th>Half-hours</th><th>Average miss</th><th>Bias</th></tr></thead>
            <tbody>
              {acc.data.by_level.map((b) => (
                <tr key={b.label}>
                  <td>{b.label}</td><td>{b.n}</td><td>{fmtMW(b.mae_mw)}</td>
                  <td className={b.bias_mw > 0 ? "over" : "under"}>{fmtMW(b.bias_mw, { sign: true })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </figure>
    </section>
  );
}
