import { useEffect, useState } from "react";
import { useApi } from "./api.js";
import { fmtDay } from "./format.js";
import ForecastView from "./ForecastView.jsx";
import AccuracyView from "./AccuracyView.jsx";

export default function App() {
  const meta = useApi("/api/meta", {});
  const [tab, setTab] = useState("buy");
  const [day, setDay] = useState(null);
  const [cutoff, setCutoff] = useState(null);

  const days = meta.data?.delivery_days ?? [];
  useEffect(() => {
    if (meta.data?.ready) {
      setDay((d) => d ?? days[Math.min(13, days.length - 1)]);
      setCutoff((c) => c ?? meta.data.default_cutoff);
    }
  }, [meta.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const idx = days.indexOf(day);

  return (
    <>
      <header className="top">
        <div className="brand">
          <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
            <path d="M3 12h18a4 4 0 1 0-4-4M3 20h24a4 4 0 1 1-4 4M3 16h12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
          <div>
            <h1>Windward</h1>
            <p>Day-ahead wind forecasts for Great Britain</p>
          </div>
        </div>

        {meta.data?.ready && (
          <div className="controls" role="group" aria-label="Forecast settings">
            <div className="field">
              <label htmlFor="day">Delivery day</label>
              <div className="stepper">
                <button onClick={() => setDay(days[idx - 1])} disabled={idx <= 0} aria-label="Previous day">‹</button>
                <select id="day" value={day ?? ""} onChange={(e) => setDay(e.target.value)}>
                  {days.map((d) => (
                    <option key={d} value={d}>{fmtDay(d)} 2026</option>
                  ))}
                </select>
                <button onClick={() => setDay(days[idx + 1])} disabled={idx >= days.length - 1} aria-label="Next day">›</button>
              </div>
            </div>
            <div className="field">
              <label htmlFor="cutoff">Decide by (day before)</label>
              <select id="cutoff" value={cutoff ?? ""} onChange={(e) => setCutoff(e.target.value)}>
                {meta.data.cutoff_options.map((c) => (
                  <option key={c} value={c}>{c} UK time</option>
                ))}
              </select>
            </div>
          </div>
        )}
      </header>

      {meta.data?.is_sample && (
        <div className="banner warn" role="alert">
          Showing <strong>synthetic sample data</strong>, not Elexon data. Run <code>python scripts/ingest.py</code> to load the real January 2026 dataset.
        </div>
      )}

      <main>
        {meta.loading && <p className="state">Loading…</p>}
        {meta.error && (
          <div className="banner err" role="alert" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
            <span>Can’t reach the API: {meta.error.message || "Connection timeout"}.</span>
            <button className="btn" onClick={() => meta.reload()} style={{ padding: "4px 14px", minHeight: "32px", fontSize: "0.9rem" }}>
              Retry
            </button>
          </div>
        )}
        {meta.data && !meta.data.ready && (
          <div className="banner err" role="alert">{meta.data.message}</div>
        )}

        {meta.data?.ready && day && cutoff && (
          <>
            <div className="tabs" role="tablist" aria-label="Views">
              <button role="tab" aria-selected={tab === "buy"} onClick={() => setTab("buy")}>Forecast for buying</button>
              <button role="tab" aria-selected={tab === "acc"} onClick={() => setTab("acc")}>How accurate is it?</button>
            </div>
            {tab === "buy" ? (
              <ForecastView day={day} cutoff={cutoff} />
            ) : (
              <AccuracyView days={days} cutoff={cutoff} />
            )}
          </>
        )}
      </main>

      <footer>
        <p>
          Wind generation: Elexon BMRS FUELHH (actual, half-hourly) and WINDFOR (forecast). Contains BMRS data © Elexon Limited.
          Times are UK local. Error = forecast − actual; positive means wind was over-forecast.
        </p>
      </footer>
    </>
  );
}
