# Wind Forecast Monitor

Web app for a GB energy utility's day-ahead buying desk. It answers two questions using national
wind data from Elexon BMRS only (FUELHH actuals, WINDFOR forecasts), for purchase decisions made in
January 2026:

1. **What is the latest wind forecast available when I have to decide?** (Day-ahead decision view)
2. **How wrong are those forecasts, quantitatively?** (Accuracy view, Lead-time view)

**Live app:** https://assignment-1-eight-chi.vercel.app/

> **AI disclosure:** this project was built with the help of an AI assistant (Claude, by Anthropic) for
> code, tests, and documentation. Design decisions and the final review are the author's responsibility.

> **Data note:** WINDFOR is published at hourly resolution, so accuracy is computed on the 24 hourly points per delivery day; FUELHH half-hours between them are ignored. Forecasts show a persistent over-forecast bias vs FUELHH wind; this may partly reflect definition/coverage differences between the datasets and should be confirmed with the client.

## Domain assumptions (please review)

| Assumption | Why / how to change |
|---|---|
| Decision for delivery day **D** is made on **D-1 at 09:00 London time** | Day-ahead auction gate closure differs by venue; this is a user-editable control in the UI (`DEFAULT_CUTOFF` in `backend/app/analysis.py`). **Confirm the real cutoff with the client.** |
| At decision time only forecasts with `publishTime <=` cutoff are usable; “per forecast point (hourly)” | Avoids look-ahead bias, the main trap in forecast evaluation |
| "Decisions in January 2026" = decision dates 1-31 Jan 2026, so delivery days 2 Jan - 1 Feb 2026 | `DECISION_START/END` in `analysis.py` |
| Error = forecast - actual. Positive = over-forecast = buyer is short | Sign convention is shown in the UI |
| Delivery day = London calendar day | Handled with `Europe/London` (GMT in January) |

## Metrics

MAE, RMSE, bias, MAE as % of mean wind, P50/P90 absolute error, and a **P90 shortfall buffer**: the MW by
which actual wind fell short of the forecast in 90% of hourly (floored at 0). It is a historical-error
guide for sizing a safety margin, not a guarantee. The "what does it mean for the buy" card needs the
user's own demand figure (no demand data is in scope).

## Layout

```
backend/app/data.py       CSV loading -> in-memory Dataset (actuals dict, forecasts by target time)
backend/app/analysis.py   Pure functions: cutoff logic, latest-forecast selection, metrics, summaries
backend/app/main.py       FastAPI routes (/api/meta, /decision/{date}, /accuracy, /horizon, /health)
backend/tests/            pytest: unit tests for the analysis + API tests
frontend/src/             React (Vite + Recharts): App.jsx (3 views), api.js, styles.css
data/                     actuals.csv, forecasts.csv, DATA_SOURCE.txt
scripts/fetch_elexon.py   Downloads real Jan 2026 data from Elexon (stdlib only)
scripts/make_synthetic.py Generates schema-identical synthetic data (dev/CI only)
api/index.py, vercel.json Vercel serverless entrypoint + build config
docker-compose.yml        backend (uvicorn) + frontend (nginx, proxies /api)
VIDEO_SCRIPT.md           Talking points for the 2-part demo video
```

## Run it

**Docker (frontend on http://localhost:8080):**

```bash
docker compose up --build
```

**Without Docker:**

```bash
# backend
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
python scripts/fetch_elexon.py          # real data (or: python scripts/make_synthetic.py)
uvicorn backend.app.main:app --reload   # run from repo root, port 8000
(cd backend && pytest)                  # tests

# frontend (separate terminal; proxies /api to :8000)
cd frontend && npm install && npm run dev
```

## Deploy to Vercel

Import the repo in Vercel (framework preset: Other). `vercel.json` builds the React app into
`frontend/dist` and serves `api/index.py` (FastAPI) for `/api/*`. The CSVs are bundled into the function, so
the deployed app does not call Elexon at runtime. Open the URL in an incognito window before submitting.

## Known limitations

- Single flat cutoff time for all days; real gate closures and DST edge cases are not modelled.
- National level only; no demand, price or probabilistic forecasts (out of scope by design).
- Data is read once at startup; refresh by re-running the fetch script and redeploying.
