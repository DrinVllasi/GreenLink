import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getAllParcels, getForecastMetrics, getForecastTable, getNotifications } from "./api";

const STATUSES = [
  "booked", "dropped_off", "matched", "loaded", "in_transit", "arrived", "collected",
];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOUR_COLORS = ["#86c99b", "#4fae71", "#2f8f57", "#1b6b3d"];

function formatTime(iso) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

// The model works in UTC hours; show them in the viewer's local time.
function localHour(hourUtc) {
  const d = new Date();
  d.setUTCHours(hourUtc, 0, 0, 0);
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

export default function AdminView() {
  const [parcels, setParcels] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [table, setTable] = useState([]);
  const [routeId, setRouteId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  function load() {
    setLoading(true);
    setError(null);
    Promise.all([getAllParcels(200), getNotifications(20)])
      .then(([p, n]) => {
        setParcels(p);
        setNotifications(n);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // the forecast is optional: if it fails, the rest of the admin screen still works
    Promise.all([getForecastMetrics(), getForecastTable()])
      .then(([mt, tb]) => {
        setMetrics(mt.ready ? mt.metrics : null);
        setTable(tb);
        setRouteId((current) => current ?? (tb.length > 0 ? tb[0].route_id : null));
      })
      .catch(() => {
        setMetrics(null);
        setTable([]);
      });
  }

  useEffect(load, []);

  const counts = {};
  STATUSES.forEach((s) => (counts[s] = 0));
  parcels.forEach((p) => {
    counts[p.status] = (counts[p.status] || 0) + 1;
  });

  // forecast data for the selected route
  const routes = [];
  table.forEach((r) => {
    if (!routes.find((x) => x.id === r.route_id)) routes.push({ id: r.route_id, name: r.route });
  });
  const rows = table.filter((r) => r.route_id === routeId);
  const hours = [...new Set(rows.map((r) => r.hour_utc))].sort((a, b) => a - b);
  const cell = (weekday, hour) => rows.find((r) => r.weekday === weekday && r.hour_utc === hour);
  const chartData = WEEKDAYS.map((wd) => {
    const point = { weekday: wd };
    hours.forEach((h) => {
      const c = cell(wd, h);
      point[localHour(h)] = c ? c.expected_fill_pct : null;
    });
    return point;
  });

  const tdStyle = { padding: "6px 8px", textAlign: "center", border: "1px solid rgba(128,128,128,0.25)" };

  return (
    <>
      <div className="card">
        <div className="admin-head">
          <h2>Parcels per status ({parcels.length} total)</h2>
          <button className="btn-secondary" onClick={load} disabled={loading}>
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
        {error && <p className="error">Could not load admin data: {error}</p>}
        <div className="tile-grid">
          {STATUSES.map((s) => (
            <div className={`tile status-${s}`} key={s}>
              <div className="stat-value">{counts[s]}</div>
              <div className="stat-label">{s.replace("_", " ")}</div>
            </div>
          ))}
        </div>
      </div>

      {metrics && (
        <div className="card">
          <h2>AI forecast: capacity-matching model</h2>
          <p className="sub">
            {metrics.label}. A simple statistical model that shows the phase-2 pipeline; the demand patterns
            are simulated, so these numbers do not represent real-world accuracy.
          </p>
          <div className="tile-grid">
            <div className="tile">
              <div className="stat-value">{metrics.fill_mae_pp} pp</div>
              <div className="stat-label">Fill forecast error (hold-out)</div>
            </div>
            <div className="tile">
              <div className="stat-value">{metrics.fill_baseline_mae_pp} pp</div>
              <div className="stat-label">Error of "predict the average"</div>
            </div>
            <div className="tile">
              <div className="stat-value">{metrics.delay_mae_min} min</div>
              <div className="stat-label">Delay forecast error (hold-out)</div>
            </div>
            <div className="tile">
              <div className="stat-value">{metrics.delay_baseline_mae_min} min</div>
              <div className="stat-label">Error of "predict the average"</div>
            </div>
          </div>
          <p className="sub">
            Trained on {metrics.train_rows} past departures and tested on the newest {metrics.holdout_days} days
            ({metrics.test_rows} departures) that it had not seen. The forecast drives the bounded price
            adjustment (at most ±15%) and a small, capped nudge in bus ranking.
          </p>

          {routes.length > 0 && (
            <>
              <label>Route
                <select value={routeId ?? ""} onChange={(e) => setRouteId(Number(e.target.value))}>
                  {routes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </label>

              <h3>Expected bus fill by weekday and departure time</h3>
              <div style={{ width: "100%", height: 260 }}>
                <ResponsiveContainer>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis dataKey="weekday" />
                    <YAxis unit="%" domain={[0, 100]} />
                    <Tooltip formatter={(v) => `${v}%`} />
                    <Legend />
                    {hours.map((h, i) => (
                      <Bar key={h} dataKey={localHour(h)} fill={HOUR_COLORS[i % HOUR_COLORS.length]} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <h3>Forecast table: expected fill % / expected delay</h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ borderCollapse: "collapse", width: "100%" }}>
                  <thead>
                    <tr>
                      <th style={tdStyle}>Day</th>
                      {hours.map((h) => <th style={tdStyle} key={h}>{localHour(h)}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {WEEKDAYS.map((wd) => (
                      <tr key={wd}>
                        <td style={tdStyle}><strong>{wd}</strong></td>
                        {hours.map((h) => {
                          const c = cell(wd, h);
                          return (
                            <td key={h} style={{
                              ...tdStyle,
                              background: c ? `rgba(46,160,90,${(c.expected_fill_pct / 100) * 0.55})` : "none",
                            }}>
                              {c ? <>{c.expected_fill_pct}% <span className="sub">/ {Math.round(c.expected_delay_min)} min</span></> : "-"}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      <div className="card">
        <h2>Notifications log (simulated SMS)</h2>
        {notifications.length === 0 && !loading && <p className="sub">No notifications yet.</p>}
        <ul className="feed">
          {notifications.map((n) => (
            <li className="feed-item" key={n.id}>
              <span className="tag">{n.channel}</span>
              <div>
                <p className="feed-msg">{n.message}</p>
                <p className="feed-meta">To {n.to} · {formatTime(n.at)}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}