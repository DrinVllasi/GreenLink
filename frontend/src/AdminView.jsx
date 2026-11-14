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