import { useEffect, useState } from "react";
import { getDepartures, getRoutes, getUsers } from "./api";
import SenderScreen from "./SenderScreen";
import ParcelHistory from "./ParcelHistory";
import ScanScreen from "./ScanScreen";

function formatTime(iso) {
  return new Date(iso).toLocaleString("en-GB", {
    weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [departures, setDepartures] = useState([]);
  const [error, setError] = useState(null);
  const [users, setUsers] = useState([]);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [currentUserId, setCurrentUserId] = useState(
    () => Number(localStorage.getItem("greenlink_user_id")) || null);
  
  useEffect(() => {
    Promise.all([getRoutes(), getDepartures(10), getUsers()])
      .then(([r, d, u]) => {
        setRoutes(r);
        setDepartures(d);
        setUsers(u);
      })
      .catch((e) => setError(e.message));
  }, []);

  const currentUser =
  users.find((u) => u.id === currentUserId) ||
  users.find((u) => u.role === "sender") ||
  null;

  function changeUser(e) {
    const id = Number(e.target.value);
    setCurrentUserId(id);
    localStorage.setItem("greenlink_user_id", String(id));
  }

  return (
    <div className="page">
      <h1>GreenLink</h1>
      <div className="role-bar">
        <label>
          Demo user:{" "}
          <select value={currentUser ? currentUser.id : ""} onChange={changeUser}>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} ({u.role})
              </option>
            ))}
          </select>
        </label>
        {currentUser && (
          <p>
            Logged in as: <strong>{currentUser.name}</strong> ({currentUser.role})
            {currentUser.business_name && ` · ${currentUser.business_name}`}
          </p>
        )}
      </div>
      <p className="sub">Frontend and backend are connected if you can see data below.</p>

      {error && <p className="error">Could not reach the API: {error}</p>}
      {currentUser && currentUser.role === "sender" && (
        <>
          <SenderScreen
            user={currentUser}
            routes={routes}
            onBooked={() => setHistoryVersion((v) => v + 1)}
          />
          <ParcelHistory userId={currentUser.id} version={historyVersion} />
        </>
      )}
      {currentUser && (currentUser.role === "driver" || currentUser.role === "agent") && (
        <ScanScreen user={currentUser} />
      )}

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
