import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getSenderImpact, getSenderSummary } from "./api";

function weekLabel(iso) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

const tooltipStyle = { background: "#fff", color: "#111", border: "1px solid #ccc", borderRadius: 6 };

function WeeklyChart({ title, data, dataKey, name, unit, color }) {
  return (
    <div>
      <h3>{title}</h3>
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.3)" />
            <XAxis dataKey="label" tick={{ fill: "currentColor", fontSize: 12 }} />
            <YAxis tick={{ fill: "currentColor", fontSize: 12 }} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(l) => `Week of ${l}`}
              formatter={(v) => [`${v}${unit}`, name]}
            />
            <Bar dataKey={dataKey} name={name} fill={color} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function SenderDashboard({ userId, version }) {
  const [summary, setSummary] = useState(null);
  const [weeks, setWeeks] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    Promise.all([getSenderSummary(userId), getSenderImpact(userId, 6)])
      .then(([s, i]) => {
        if (cancelled) return;
        setSummary(s);
        setWeeks(
          i.weeks.map((w) => ({
            label: weekLabel(w.week_start),
            co2: w.co2_avoided_kg,
            credits: w.credits_earned,
          }))
        );
      })
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [userId, version]);

  if (error) return <div className="card"><p className="error">Could not load dashboard: {error}</p></div>;
  if (!summary) return <div className="card"><p>Loading dashboard…</p></div>;

  const stats = [
    { label: "Parcels sent", value: summary.parcels_total },
    { label: "In progress", value: summary.parcels_in_progress },
    { label: "Spent", value: `${summary.total_spent_eur.toFixed(2)} EUR` },
    { label: "CO2 avoided", value: `${summary.co2_avoided_kg} kg` },
    { label: "Green credits", value: `${summary.credits_balance} (${summary.credits_value_eur.toFixed(2)} EUR)` },
  ];

  return (
    <div className="card">
      <h2>{summary.sender}: impact dashboard</h2>
      <div className="stats">
        {stats.map((s) => (
          <div className="stat" key={s.label}>
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>
      <div className="chart-grid">
        <WeeklyChart title="CO2 avoided per week" data={weeks} dataKey="co2" name="CO2 avoided" unit=" kg" color="#2e7d32" />
        <WeeklyChart title="Credits earned per week" data={weeks} dataKey="credits" name="Credits earned" unit=" credits" color="#66bb6a" />
      </div>
    </div>
  );
}