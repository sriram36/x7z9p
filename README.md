# Windward: Day-Ahead Wind Forecast Desk for UK Power Procurement

A web application developed for a UK energy utility procurement team purchasing wholesale electricity on the **day-ahead market** to meet consumer demand.

Utility buyers must determine how much power must be additionally procured (e.g. from thermal or flexible generation) beyond what renewable sources like wind will supply. Because renewable output is weather-dependent and day-ahead auction bids must be submitted on the day before delivery (**D-1**), buyers require:
1. **Latest actionable forecast before gate closure**: Exactly what the wind forecast predicts for tomorrow at decision time (strictly excluding look-ahead forecasts published later).
2. **Quantified forecast error**: Statistical bounds and empirical shortfall risk (e.g., 1-in-20 over-forecast risk) to size their thermal procurement buffers without overpaying or facing balancing penalties.

- **Repository:** https://github.com/sriram36/x7z9p
- **Live URL:** https://x7z9p-yxu2.vercel.app/
- **Data Source:** Elexon BMRS (Insights Solution) API: `FUELHH` (actual wind, half-hourly) and `WINDFOR` (wind forecast, with publish time). Contains BMRS data © Elexon Limited.
- **Technology Stack:** React (Vite, Recharts) · Python (FastAPI, pure standard library analytics) · Docker · Vercel

> **AI Disclosure:** This project was developed with the assistance of AI tools (Claude and Gemini via Google DeepMind Antigravity). All architectural choices, domain logic, temporal conversions, and error models were rigorously reviewed, debugged, and tested.

---

## What It Does

| View | Answers for the Utility Buyer |
|---|---|
| **Forecast for buying** | For delivery day **D** and decision cutoff on **D-1** (default 09:00 UK local time), shows the latest wind forecast published prior to cutoff, expected daily GWh, peak/trough MW, empirical 5th–95th percentile risk band, and an optional toggle to audit against actual outturn (`FUELHH`). |
| **How accurate is it?** | Quantifies forecast error: MAE, RMSE, bias, 90th percentile miss, and the crucial **1-in-20 over-forecast** (shortfall to cover with thermal units). Breaks error down across delivery days, forecast lead times (how waiting improves accuracy), hours of the day (diurnal bias), and wind output levels. |

### Key Modelling & Domain Principles

- **No Look-Ahead Bias:** Day-ahead bids are placed on D-1. For every slot of day D, the engine selects the latest forecast row where `publishTime <= cutoff` (e.g. 09:00 UK time on D-1). Any forecast published at 09:01 or later is ignored for that day's buying decision.
- **Hourly vs. Half-Hourly Resolution:** In Elexon BMRS, `FUELHH` outturn is half-hourly (30 min), whereas transmission-connected `WINDFOR` forecasts are hourly (60 min). The store maps hourly forecasts cleanly across half-hourly settlement periods (`:00` and `:30`), ensuring exact energy conservation ($1\text{ MW} \times 0.5\text{ h} = 0.5\text{ MWh}$).
- **Timezone & DST Rigour:** Timestamps are stored in UTC. Cutoff times and delivery days operate in UK local time (`Europe/London`), handling standard 48-slot days as well as 46/50-slot DST transition days.
- **Utility-Centric Error Convention:** $\text{Error} = \text{Forecast} - \text{Actual}$. A positive error is an **over-forecast**—the dangerous failure mode where wind falls short of expectations and the buyer is caught short, forced to buy expensive power at real-time cashout/balancing mechanism prices.
- **Why No MAPE:** Wind generation frequently nears zero, which causes Mean Absolute Percentage Error (MAPE) to divide by near-zero numbers and explode. Normalised MAE (% of mean actual output) is reported instead.
- **Likely Range Band:** Sized using empirical 5th–95th percentiles of $(\text{Actual} - \text{Forecast})$ calculated exclusively from preceding delivery days (what a buyer could have known in real time).

---

## How to Start the Application

### Option A: Local Development

```bash
# 1. Backend (Python 3.10+)
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000

# 2. Frontend (Node.js 18+)
cd frontend
npm install
npm run dev
# Open http://localhost:5173 (proxies /api to http://localhost:8000)
```

### Option B: Docker Compose

```bash
docker compose up --build
# Open http://localhost:8080 (frontend proxies /api requests to backend:8000)
```

### Option C: Re-running Data Ingestion

The repository already comes with the committed January 2026 Elexon snapshot in `data/`. If you wish to re-pull fresh data from Elexon:

```bash
python scripts/ingest.py
```

### Running Backend Tests

```bash
pip install -r requirements-dev.txt
pytest backend/tests -q
# 19 passing tests covering cutoff invariants, no-look-ahead, DST transitions, metrics, and API contracts.
```

---

## Deploying to Vercel (Vercel Services)

The repository is configured for **Vercel Services** in `vercel.json`:
1. Commit all files (including the committed `data/` snapshot).
2. Import the repository in [Vercel](https://vercel.com) (root `./`).
3. Vercel automatically deploys two coordinated services:
   - **`frontend`** (Vite + React SPA) serving the public web application at `/(.*)`
   - **`backend`** (Python FastAPI) serving the public API endpoints at `/api/(.*)` with entrypoint `backend.app.main:app`
4. Use `vercel dev` locally to run all services together with automated proxy routing.

---

## Files and Directories Present

| Path | Purpose |
|---|---|
| **`backend/`** | Python backend package |
| `backend/app/main.py` | FastAPI application exposing `/api/meta`, `/api/forecast`, `/api/accuracy`, `/api/horizon` |
| `backend/app/store.py` | In-memory data store with $O(\log N)$ `bisect_right` forecast-as-of lookups and hourly-to-half-hourly mapping |
| `backend/app/analysis.py` | Pure calculation functions: error metrics, empirical confidence bands, lead time and diurnal bucketing |
| `backend/app/timeutil.py` | UTC and `Europe/London` conversions, settlement slot generation, and D-1 cutoff calculations |
| `backend/app/config.py` | Directory paths and default cutoff parameters (07:00–11:00) |
| `backend/tests/` | Automated test suite (19 tests covering cutoff invariants, metrics, DST, and API schemas) |
| `backend/Dockerfile` | Production container definition for FastAPI |
| **`frontend/`** | React + Vite frontend application |
| `frontend/src/App.jsx` | Main application shell, header, day/cutoff controls, and tab navigation |
| `frontend/src/ForecastView.jsx` | Day-ahead forecast chart (Recharts), likely-range area, peak/low KPIs, and actuals comparison toggle |
| `frontend/src/AccuracyView.jsx` | Quantitative accuracy analytics: MAE, RMSE, Bias, P95 shortfall, Error vs Lead Time, Bias by Hour |
| `frontend/src/api.js` | Fetch hook with abort controller and error handling |
| `frontend/src/format.js` | Number and date formatters (GW/MW scaling, nice axis tick generator, CSV download) |
| `frontend/src/styles.css` | Bespoke styling with CSS variables, accessible high-contrast dark/light modes, and responsive layout |
| `frontend/Dockerfile` | Multi-stage Docker build producing an optimized Nginx container |
| `frontend/nginx.conf` | Nginx reverse-proxy configuration routing `/api/` to backend |
| **`data/`** | Committed January 2026 Elexon data snapshot |
| `data/actuals_wind.csv` | January 2026 half-hourly actual wind generation (`FUELHH`, 1,488 rows) |
| `data/windfor.csv.gz` | January 2026 hourly wind forecasts with publish timestamps (`WINDFOR`, 14,383 rows) |
| `data/meta.json` | Dataset provenance, timestamp metadata, and attribution |
| **`scripts/`** | Utilities and ingestion scripts |
| `scripts/ingest.py` | Live Elexon BMRS API streaming ingest script for January 2026 snapshot |
| `scripts/make_sample_data.py` | Offline synthetic test data generator (for isolated development) |
| **`api/index.py`** | Vercel serverless function entrypoint |
| **`vercel.json`** | Monorepo build and serverless routing configuration for Vercel |
| **`docker-compose.yml`** | Multi-container orchestration (backend on :8000, frontend on :8080) |
| **`Makefile`** | Convenience shortcuts for install, test, dev, and build |
