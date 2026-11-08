import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { scanParcel } from "./api";

function formatTime(iso) {
  return new Date(iso).toLocaleString("en-GB", {
    weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export default function ScanScreen({ user }) {
  const [code, setCode] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [recent, setRecent] = useState([]);
  const scannerRef = useRef(null);
  const lockRef = useRef(false);

  async function stopCamera() {
    const s = scannerRef.current;
    scannerRef.current = null;
    setCameraOn(false);
    if (s) {
      try { await s.stop(); s.clear(); } catch (e) { /* already stopped */ }
    }
  }

  // turn the camera off when leaving this screen
  useEffect(() => () => { stopCamera(); }, []);

  async function doScan(raw) {
    const c = raw.trim().toUpperCase();
    if (!c) { setError("Enter or scan a parcel code."); return; }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await scanParcel(c);
      setResult(r);
      const p = r.parcel || r;
      setRecent((list) =>
        [{ code: p.code, status: p.status, at: new Date().toISOString() }, ...list].slice(0, 5));
      setCode("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function startCamera() {
    setCameraError(null);
    lockRef.current = false;
    try {
      const scanner = new Html5Qrcode("reader");
      scannerRef.current = scanner;
      await scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 220, height: 220 } },
        (text) => {
          if (lockRef.current) return; // the camera reports the same code many times
          lockRef.current = true;
          stopCamera();
          setCode(text);
          doScan(text);
        },
        () => {} // ignore frames without a readable code
      );
      setCameraOn(true);
    } catch (e) {
      scannerRef.current = null;
      setCameraError(
        "Camera not available. It needs permission and https (or localhost). Use the manual field below.");
    }
  }

  const parcel = result && (result.parcel || result);

  return (
    <div className="card">
      <h2>Scan a parcel</h2>
      <p className="sub">Scanning as {user.name} ({user.role}). Each scan moves the parcel to its next step.</p>

      <div id="reader"></div>
      {cameraError && <p className="error">{cameraError}</p>}
      {!cameraOn ? (
        <button onClick={startCamera} disabled={busy}>Start camera</button>
      ) : (
        <button onClick={stopCamera}>Stop camera</button>
      )}

      <div className="form-grid" style={{ marginTop: "1rem" }}>
        <label>Or type the parcel code
          <input value={code} placeholder="GL-123456"
            onChange={(e) => setCode(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") doScan(code); }} />
        </label>
        <button onClick={() => doScan(code)} disabled={busy}>
          {busy ? "Scanning..." : "Scan"}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {parcel && (
        <div className="quote-box">
          <h3>{result.message || "Scanned"}</h3>
          <p>
            <strong>{parcel.code}</strong>{" "}
            <span className={`pill status-${parcel.status}`}>{parcel.status.replace("_", " ")}</span>
          </p>
          <p>{parcel.origin} → {parcel.destination} · {parcel.weight_kg} kg · To: {parcel.receiver_name}</p>
          {parcel.departure && (
            <p>Bus: {parcel.departure.operator}, departs {formatTime(parcel.departure.departs_at)}
              {" "}({parcel.departure.booked_kg}/{parcel.departure.capacity_kg} kg booked)</p>
          )}
          {result.matched === false && (
            <p className="error">No bus with free space yet. Scan again later to retry matching.</p>
          )}
        </div>
      )}

      {recent.length > 0 && (
        <>
          <h3>Recent scans</h3>
          <ul>
            {recent.map((r, i) => (
              <li key={i}>{r.code} → {r.status.replace("_", " ")} · {formatTime(r.at)}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}