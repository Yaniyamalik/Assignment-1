import React, { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "./api.js";

const fmt = (v, d = 0) => (v == null ? "–" : Number(v).toLocaleString("en-GB", { maximumFractionDigits: d }));
const COLORS = { forecast: "#2563eb", actual: "#16a34a", error: "#dc2626", bias: "#9333ea" };

function useLoad(fn, deps) {
  const [state, set] = useState({ loading: true, data: null, error: null });
  useEffect(() => {
    let live = true;
    set((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => live && set({ loading: false, data, error: null }))
      .catch((error) => live && set({ loading: false, data: null, error: error.message }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

function Stat({ label, value, unit, hint }) {
  return (
    <div className="stat" title={hint}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}<span className="unit">{unit}</span></div>
    </div>
  );
}

function Status({ s }) {
  if (s.loading) return <p className="muted">Loading…</p>;
  if (s.error) return <p className="error">Could not load data: {s.error}</p>;
  return null;
}

function MetricCards({ m }) {
  if (!m) return <p className="muted">No overlapping forecast and actual data.</p>;
  return (
    <div className="stats">
      <Stat label="MAE" value={fmt(m.mae)} unit=" MW" hint="Mean absolute error" />
      <Stat label="RMSE" value={fmt(m.rmse)} unit=" MW" hint="Penalises large misses more" />
      <Stat label="Bias" value={fmt(m.bias)} unit=" MW" hint="Mean (forecast − actual). Positive = wind over-forecast" />
      <Stat label="MAE % of mean wind" value={fmt(m.nmae_pct, 1)} unit="%" />
      <Stat label="P90 abs. error" value={fmt(m.p90_abs_error)} unit=" MW" hint="9 in 10 half-hours miss by less than this" />
      <Stat label="P90 shortfall buffer" value={fmt(m.buffer_p90)} unit=" MW"
        hint="In 90% of half-hours actual wind was no more than this far below forecast" />
    </div>
  );
}

const timeLabel = (iso) =>
  new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });

function DecisionView({ meta, cutoff }) {
  const [day, setDay] = useState(meta.deliveryDays[13]);
  const [demand, setDemand] = useState("");
  const s = useLoad(() => api.decision(day, cutoff), [day, cutoff]);
  const { data } = s;
  const rows = data?.rows.map((r) => ({ ...r, t: timeLabel(r.startTime) })) ?? [];
  const buffer = data?.metrics?.buffer_p90 ?? 0;
  const d = parseFloat(demand);
  const withF = rows.filter((r) => r.forecast != null);
  const avgF = withF.length ? withF.reduce((a, r) => a + r.forecast, 0) / withF.length : null;

  return (
    <section>
      <div className="controls">
        <label>Delivery day
          <select value={day} onChange={(e) => setDay(e.target.value)}>
            {meta.deliveryDays.map((x) => <option key={x}>{x}</option>)}
          </select>
        </label>
        {data && (
          <span className="muted">
            Decision made {data.decisionDate} at {cutoff} (London). Using the latest forecast published on or before{" "}
            {new Date(data.cutoffUtc).toLocaleString("en-GB", { timeZone: "Europe/London" })}.
          </span>
        )}
      </div>
      <Status s={s} />
      {data && (
        <>
          <div className="card">
            <h3>Wind forecast available at decision time vs actual</h3>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="t" interval={5} />
                <YAxis tickFormatter={(v) => `${v / 1000}`} label={{ value: "GW", angle: -90, position: "insideLeft" }} />
                <Tooltip formatter={(v) => `${fmt(v)} MW`} />
                <Legend />
                <Line dataKey="forecast" name="Forecast (D-1)" stroke={COLORS.forecast} dot={false} strokeWidth={2} connectNulls />
                <Line dataKey="actual" name="Actual" stroke={COLORS.actual} dot={false} strokeWidth={2} connectNulls />
              </LineChart>
            </ResponsiveContainer>
            <p className="muted small">
              Coverage: {data.coverage.withForecast}/{data.coverage.slots} half-hours have a forecast,{" "}
              {data.coverage.withActual}/{data.coverage.slots} have an actual.
            </p>
          </div>

          <div className="card">
            <h3>How accurate was this day's forecast?</h3>
            <MetricCards m={data.metrics} />
          </div>

          <div className="card">
            <h3>What does that mean for the buy? (illustrative)</h3>
            <p className="muted small">
              Demand is outside this tool's data scope, so enter your own flat demand estimate to see the residual that
              wind does not cover, with and without a historical-error buffer.
            </p>
            <label>Expected demand (MW)
              <input type="number" min="0" value={demand} placeholder="e.g. 30000" onChange={(e) => setDemand(e.target.value)} />
            </label>
            {Number.isFinite(d) && avgF != null && (
              <div className="stats">
                <Stat label="Avg. forecast wind" value={fmt(avgF)} unit=" MW" />
                <Stat label="Residual to procure" value={fmt(Math.max(d - avgF, 0))} unit=" MW" hint="demand − forecast wind" />
                <Stat label="…with P90 buffer" value={fmt(Math.max(d - avgF + buffer, 0))} unit=" MW"
                  hint="Adds the day's P90 over-forecast error as safety margin" />
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function AccuracyView({ cutoff }) {
  const s = useLoad(() => api.accuracy(cutoff), [cutoff]);
  const { data } = s;
  if (!data) return <Status s={s} />;
  const daily = data.daily.map((x) => ({ day: x.deliveryDate.slice(5), mae: x.metrics?.mae, bias: x.metrics?.bias }));
  const hourly = data.hourly.map((x) => ({ hour: `${String(x.hour).padStart(2, "0")}:00`, mae: x.metrics.mae, bias: x.metrics.bias }));
  const hist = data.histogram.map((b) => ({ bin: `${b.from / 1000}`, count: b.count }));
  return (
    <section>
      <div className="card">
        <h3>January 2026, all day-ahead decisions (cutoff {data.cutoff} London, D-1)</h3>
        <MetricCards m={data.overall} />
      </div>
      <div className="card">
        <h3>Daily error</h3>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={daily}>
            <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="day" /><YAxis /><Tooltip formatter={(v) => `${fmt(v)} MW`} /><Legend />
            <Bar dataKey="mae" name="MAE" fill={COLORS.forecast} />
            <Line dataKey="bias" name="Bias" stroke={COLORS.bias} dot />
            <ReferenceLine y={0} stroke="#888" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <h3>Error by hour of day (London)</h3>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={hourly}>
            <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="hour" interval={1} /><YAxis /><Tooltip formatter={(v) => `${fmt(v)} MW`} /><Legend />
            <Bar dataKey="mae" name="MAE" fill={COLORS.forecast} />
            <Line dataKey="bias" name="Bias" stroke={COLORS.bias} dot />
            <ReferenceLine y={0} stroke="#888" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <h3>Distribution of forecast error (forecast − actual)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={hist}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="bin" label={{ value: "error bin start (GW)", position: "insideBottom", offset: -4 }} />
            <YAxis /><Tooltip /><Bar dataKey="count" name="Half-hours" fill={COLORS.error} />
          </BarChart>
        </ResponsiveContainer>
        <p className="muted small">Right of zero = wind over-forecast (buyer short). Left = under-forecast (buyer long).</p>
      </div>
    </section>
  );
}

function HorizonView() {
  const s = useLoad(() => api.horizon(), []);
  const { data } = s;
  if (!data) return <Status s={s} />;
  const rows = data.buckets.map((b) => ({ lead: `${b.fromHours}–${b.toHours}h`, mae: b.metrics.mae, rmse: b.metrics.rmse, bias: b.metrics.bias }));
  return (
    <section>
      <div className="card">
        <h3>Forecast error vs lead time (all forecasts published in January 2026)</h3>
        <p className="muted small">Lead time = target time − publish time. Shows how much the forecast improves as delivery approaches.</p>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="lead" /><YAxis /><Tooltip formatter={(v) => `${fmt(v)} MW`} /><Legend />
            <Line dataKey="mae" name="MAE" stroke={COLORS.forecast} strokeWidth={2} />
            <Line dataKey="rmse" name="RMSE" stroke={COLORS.error} strokeWidth={2} />
            <Line dataKey="bias" name="Bias" stroke={COLORS.bias} strokeDasharray="4 3" />
            <ReferenceLine y={0} stroke="#888" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export default function App() {
  const [tab, setTab] = useState("decision");
  const [cutoff, setCutoff] = useState("09:00");
  const m = useLoad(() => api.meta(), []);
  useEffect(() => { if (m.data) setCutoff(m.data.defaultCutoff); }, [m.data]);

  return (
    <div className="app">
      <header>
        <h1>Wind Forecast Monitor</h1>
        <p>GB national wind generation: day-ahead forecast vs actual, January 2026 (Elexon BMRS)</p>
      </header>
      {m.data?.dataSource === "synthetic" && (
        <div className="banner">Demo build: this instance is running on SYNTHETIC data, not Elexon data.</div>
      )}
      <Status s={m} />
      {m.data && (
        <>
          <nav>
            {[["decision", "Day-ahead decision"], ["accuracy", "Accuracy"], ["horizon", "Lead time"]].map(([k, l]) => (
              <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}</button>
            ))}
            <label className="cutoff">Decision cutoff (London, D-1)
              <input type="time" value={cutoff} onChange={(e) => e.target.value && setCutoff(e.target.value)} />
            </label>
          </nav>
          {tab === "decision" && <DecisionView meta={m.data} cutoff={cutoff} />}
          {tab === "accuracy" && <AccuracyView cutoff={cutoff} />}
          {tab === "horizon" && <HorizonView />}
        </>
      )}
    </div>
  );
}
