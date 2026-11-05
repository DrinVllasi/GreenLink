import { useEffect, useState } from "react";
import { getDepartures, getRoutes } from "./api";

function formatTime(iso) {
  return new Date(iso).toLocaleString("en-GB", {
    weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [departures, setDepartures] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getRoutes(), getDepartures(10)])
      .then(([r, d]) => {
        setRoutes(r);
        setDepartures(d);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="page">
      <h1>GreenLink</h1>
      <p className="sub">Frontend and backend are connected if you can see data below.</p>

      {error && <p className="error">Could not reach the API: {error}</p>}

      <h2>Routes ({routes.length})</h2>
      <ul>
        {routes.map((r) => (
          <li key={r.id}>
            {r.origin} → {r.destination} ({r.distance_km} km)
          </li>
        ))}
      </ul>

      <h2>Next departures</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Route</th>
              <th>Departs</th>
              <th>Operator</th>
              <th>Free space</th>
            </tr>
          </thead>
          <tbody>
            {departures.map((d) => (
              <tr key={d.id}>
                <td>{d.origin} → {d.destination}</td>
                <td>{formatTime(d.departs_at)}</td>
                <td>{d.operator}</td>
                <td>{d.free_kg} kg</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
