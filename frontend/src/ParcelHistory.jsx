import { Fragment, useEffect, useState } from "react";
import { getParcels, getParcel } from "./api";

function formatTime(iso) {
  return new Date(iso).toLocaleString("en-GB", {
    weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

const STEPS = ["Booked", "At station", "On bus", "Arrived", "Collected"];
const STEP_OF = {
  booked: 0, dropped_off: 1, matched: 1, loaded: 2, in_transit: 2, arrived: 3, collected: 4,
};

function Tracker({ status }) {
  const current = STEP_OF[status] ?? 0;
  return (
    <ol className="tracker">
      {STEPS.map((s, i) => (
        <li key={s} className={(i <= current ? "done " : "") + (i === current ? "current" : "")}>
          {s}
        </li>
      ))}
    </ol>
  );
}

function Details({ details }) {
  return (
    <div className="details" onClick={(e) => e.stopPropagation()}>
      <Tracker status={details.status} />
      <p>Pickup code for the receiver: <span className="code-big">{details.pickup_code}</span></p>
      {details.departure && (
        <p>Bus: {details.departure.operator}, departs {formatTime(details.departure.departs_at)}</p>
      )}
      <ul>
        {(details.events || []).map((ev, i) => (
          <li key={i}>
            <strong>{ev.status.replace("_", " ")}</strong> · {formatTime(ev.at)}
            {ev.note && <span className="sub"> · {ev.note}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ParcelHistory({ userId, version }) {
  const [parcels, setParcels] = useState([]);
  const [error, setError] = useState(null);
  const [openCode, setOpenCode] = useState(null);
  const [details, setDetails] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getParcels(userId)
      .then((list) => {
        if (cancelled) return;
        const arr = Array.isArray(list) ? list : (list.parcels || []);
        arr.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        setParcels(arr);
        setError(null);
      })
      .catch((e) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [userId, version]);

  function toggle(code) {
    if (openCode === code) {
      setOpenCode(null);
      setDetails(null);
      return;
    }
    setOpenCode(code);
    setDetails(null);
    getParcel(code)
      .then((r) => setDetails(r.parcel || r))
      .catch((e) => setError(e.message));
  }

  function renderDetails(code) {
    if (openCode !== code) return null;
    return details ? <Details details={details} /> : <p className="sub">Loading...</p>;
  }

  const shown = parcels.slice(0, 15);

  return (
    <div className="card">
      <h2>My parcels ({parcels.length})</h2>
      {error && <p className="error">{error}</p>}
      {parcels.length === 0 && !error && <p className="sub">No parcels yet.</p>}

      {parcels.length > 0 && (
        <>
          <div className="table-wrap only-desktop">
            <table>
              <thead>
                <tr>
                  <th>Code</th><th>Route</th><th>Weight</th>
                  <th>Receiver</th><th>Status</th><th>Booked</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((p) => (
                  <Fragment key={p.code}>
                    <tr className="clickable" onClick={() => toggle(p.code)}>
                      <td>{p.code}</td>
                      <td>{p.origin} → {p.destination}</td>
                      <td>{p.weight_kg} kg</td>
                      <td>{p.receiver_name}</td>
                      <td><span className={`pill status-${p.status}`}>{p.status.replace("_", " ")}</span></td>
                      <td>{formatTime(p.created_at)}</td>
                    </tr>
                    {openCode === p.code && (
                      <tr><td colSpan="6">{renderDetails(p.code)}</td></tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

          <div className="only-mobile">
            {shown.map((p) => (
              <div className="parcel-card" key={p.code} onClick={() => toggle(p.code)}>
                <div className="pc-top">
                  <strong>{p.code}</strong>
                  <span className={`pill status-${p.status}`}>{p.status.replace("_", " ")}</span>
                </div>
                <p className="sub">{p.origin} → {p.destination} · {p.weight_kg} kg</p>
                <p className="sub">To {p.receiver_name} · {formatTime(p.created_at)}</p>
                {renderDetails(p.code)}
              </div>
            ))}
          </div>
        </>
      )}
      {parcels.length > 15 && <p className="sub">Showing the latest 15.</p>}
    </div>
  );
}