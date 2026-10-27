# Video script (max 10 min total)

Record against the real Elexon data (no amber "SYNTHETIC" banner on screen), ideally on the deployed Vercel URL.
Numbers marked "about" are read off the charts; re-check them on screen before you say them.

Headline numbers (January 2026, cutoff 09:00 London on D-1):
- MAE 2,022 MW | RMSE 2,497 MW | Bias +1,746 MW | MAE is 17.9% of mean wind (mean is about 11.3 GW)
- P90 absolute error 4,154 MW | P90 shortfall buffer 4,154 MW

---

## Part 1: Customer pitch (about 4.5 min)

**1. Problem (0:30)**
"Your desk buys day-ahead power the day before delivery. Wind is weather-dependent, so every buy rests on a forecast.
This pilot answers two questions: what is the latest wind forecast I have when I must decide, and how far can I trust it?
It uses national wind data from Elexon only, for decisions made in January 2026."

**2. Day-ahead decision tab (1:30)**
- Pick a delivery day (e.g. 15 Jan). "Decision made on 14 Jan at 09:00 London. Blue is the forecast you actually had
  at that moment, green is what the wind really did."
- Show the cutoff control: "You can move the cutoff to match your real gate closure, and everything recalculates."
- Point at the coverage line: "The forecast feed is hourly, so 24 forecast points per day."
- Show the day's accuracy cards (MAE, bias).
- Type a demand figure into the buy card: "Residual you would procure, and the same with a P90 safety buffer."

**3. Accuracy tab (1:30)**
- "Across January, the average miss is about 2.0 GW, roughly 18% of mean wind. In 9 out of 10 hours, wind fell short
  of the forecast by no more than about 4.2 GW, so that is a historical guide for a safety buffer."
- **Key finding:** "Bias is +1.7 GW. The forecast is not just noisy, it leans high: wind came in below forecast
  more often than above. For a buyer, that means being short and having to cover the gap."
- Daily chart: "Most days are within 1-2 GW, but 11-12 Jan and 28 Jan missed by about 5 GW. Those are the days
  where a buffer matters most."
- Hourly chart and histogram: describe what you see on screen (time-of-day pattern; right of zero = over-forecast).

**4. Lead time tab (0:45)**
"Forecasts improve as delivery approaches: about 1.75 GW error within 6 hours versus about 2.3 GW at 2 days out.
Even the closest forecasts carry a bias of about 1.5 GW, which suggests a systematic offset, not just forecast skill.
That is the first thing I would investigate with you: whether the forecast and the metered wind are defined on the same basis."

**5. Close (0:15)**
"Next steps: confirm your real cutoff, add your demand data so the buy card uses real numbers, move to probabilistic
buffers, and automate the daily data refresh."

---

## Part 2: Tech-lead review (about 4.5 min)

**1. Architecture (1:00)**
CSVs -> `data.py` (in-memory Dataset) -> `analysis.py` (pure functions) -> FastAPI -> React (Vite + Recharts).
"No database on purpose: one month is about 1.5k actual points and about 20k forecast rows, read-only. Data comes
from `scripts/fetch_elexon.py` (stdlib only) and is committed, so the deployed app never calls Elexon at runtime."

**2. Key logic (1:30)** (open `analysis.py`)
- `cutoff_utc`: D-1 at the cutoff in Europe/London, converted to UTC.
- `latest_forecast`: bisect on sorted publish times, so only forecasts published at or before the cutoff are used
  (no look-ahead bias).
- `metrics`: error = forecast - actual; MAE, RMSE, bias, percentiles, P90 shortfall buffer.
- `horizon_summary`: error bucketed by lead time (target time - publish time).
- Data fact: WINDFOR is hourly, FUELHH is half-hourly, so scoring only happens on the hours where both exist.
- Flag the cutoff (09:00) as an assumption to confirm with the client.

**3. Quality (1:00)**
"13 pytest tests: hand-computed metric values, cutoff-respecting selection, error sign, empty inputs, and API
validation (422 for a bad cutoff, 404 outside the January window). Frontend has no automated tests yet, which is
a known gap. A banner appears if the data is marked synthetic, so demo data cannot be mistaken for real data."

**4. Ops (0:45)**
`docker compose up --build` (backend uvicorn, frontend nginx proxying /api). Vercel: `vercel.json` builds the React
app and `api/index.py` exposes FastAPI. README discloses that AI tools were used.

**5. Limitations / next steps (0:15)**
Flat cutoff for all days, no DST edge cases, data loaded once at startup, no frontend tests, and the bias vs
metered wind needs a definition check.