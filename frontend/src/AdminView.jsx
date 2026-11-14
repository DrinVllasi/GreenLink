import { useEffect, useState } from "react";
import { getAllParcels, getNotifications } from "./api";

const STATUSES = [
  "booked", "dropped_off", "matched", "loaded", "in_transit", "arrived", "collected",
];

function formatTime(iso) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

export default function AdminView() {
  const [parcels, setParcels] = useState([]);
  const [notifications, setNotifications] = useState([]);
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
  }

  useEffect(load, []);

  const counts = {};
  STATUSES.forEach((s) => (counts[s] = 0));
  parcels.forEach((p) => {
    counts[p.status] = (counts[p.status] || 0) + 1;
  });

  return (
    <div className="card">
      <h2>Admin overview</h2>
      <button onClick={load} disabled={loading}>
        {loading ? "Loading..." : "Refresh"}
      </button>
      {error && <p className="error">Could not load admin data: {error}</p>}

      <h3>Parcels per status ({parcels.length} total)</h3>
      <div className="stats">
        {STATUSES.map((s) => (
          <div className="stat" key={s}>
            <div className="stat-value">{counts[s]}</div>
            <div className="stat-label">{s.replace("_", " ")}</div>
          </div>
        ))}
      </div>

      <h3>Notifications log (simulated SMS)</h3>
      {notifications.length === 0 && !loading && <p>No notifications yet.</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>To</th>
              <th>Channel</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {notifications.map((n) => (
              <tr key={n.id}>
                <td>{formatTime(n.at)}</td>
                <td>{n.to}</td>
                <td>{n.channel}</td>
                <td>{n.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}