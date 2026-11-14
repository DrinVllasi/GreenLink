import { useEffect, useState } from "react";
import { getRoutes, getUsers } from "./api";
import SenderScreen from "./SenderScreen";
import ParcelHistory from "./ParcelHistory";
import ScanScreen from "./ScanScreen";
import PickupScreen from "./PickupScreen";
import SenderDashboard from "./SenderDashboard";
import AdminView from "./AdminView";

const WELCOME = {
  sender: {
    title: (u) => `Welcome back, ${u.business_name || u.name}`,
    text: "Book a parcel, follow it on the bus and watch your CO2 savings grow.",
  },
  driver: {
    title: (u) => `Driver view: ${u.name}`,
    text: "Scan each parcel when you load it and when it arrives. One scan always means the next step.",
  },
  agent: {
    title: (u) => `Station desk: ${u.name}`,
    text: "Scan arriving parcels, then hand them over with the receiver's pickup code.",
  },
  admin: {
    title: () => "Operations overview",
    text: "Live parcel counts and the simulated SMS log.",
  },
};

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [error, setError] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [slow, setSlow] = useState(false);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [currentUserId, setCurrentUserId] = useState(
    () => Number(localStorage.getItem("greenlink_user_id")) || null);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 4000);
    Promise.all([getRoutes(), getUsers()])
      .then(([r, u]) => {
        setRoutes(r);
        setUsers(u);
      })
      .catch((e) => setError(e.message))
      .finally(() => {
        clearTimeout(timer);
        setLoading(false);
      });
    return () => clearTimeout(timer);
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
    <>
      <header className="app-header">
        <div className="header-inner">
          <div className="brand">
            <span className="brand-name"><span className="brand-mark" />GreenLink</span>
            <span className="brand-sub">Small parcels on buses already running</span>
          </div>
          <div className="role-switch">
            <label>
              Demo user
              <select value={currentUser ? currentUser.id : ""} onChange={changeUser}>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.role})
                  </option>
                ))}
              </select>
            </label>
            {currentUser && <span className="role-badge">{currentUser.role}</span>}
          </div>
        </div>
      </header>

      <div className="page">
        {loading && slow && (
          <p className="notice">
            Waking up the server, this can take up to a minute. Please wait...
          </p>
        )}
        {error && <p className="error">Could not load data: {error}</p>}
        {currentUser && WELCOME[currentUser.role] && (
          <div className="welcome">
            <h1>{WELCOME[currentUser.role].title(currentUser)}</h1>
            <p>{WELCOME[currentUser.role].text}</p>
          </div>
        )}

        {currentUser && currentUser.role === "sender" && (
          <>
            <SenderDashboard userId={currentUser.id} version={historyVersion} />
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
        {currentUser && currentUser.role === "agent" && <PickupScreen />}
        {currentUser && currentUser.role === "admin" && <AdminView />}
      </div>
    </>
  );
}