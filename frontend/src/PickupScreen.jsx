import { useState } from "react";
import { collectParcel } from "./api";

export default function PickupScreen() {
  const [code, setCode] = useState("");
  const [pickupCode, setPickupCode] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleCollect() {
    const c = code.trim().toUpperCase();
    const p = pickupCode.trim();
    if (!c || !p) {
      setError("Enter the parcel code and the receiver's pickup code.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await collectParcel(c, p);
      setResult(r);
      setCode("");
      setPickupCode("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const parcel = result && result.parcel;

  return (
    <div className="card">
      <h2>Hand over to receiver</h2>
      <p className="sub">The parcel must have status "arrived". The receiver tells you their pickup code.</p>

      <div className="form-grid">
        <label>Parcel code
          <input value={code} placeholder="GL-123456"
            onChange={(e) => setCode(e.target.value)} />
        </label>
        <label>Receiver's pickup code
          <input value={pickupCode} inputMode="numeric" placeholder="4 digits"
            onChange={(e) => setPickupCode(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleCollect(); }} />
        </label>
        <button onClick={handleCollect} disabled={busy}>
          {busy ? "Checking..." : "Confirm handover"}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="result-card">
          <div className="success-icon">✓</div>
          <h3>Parcel handed over</h3>
          {parcel && (
            <>
              <span className={`pill big-pill status-${parcel.status}`}>{parcel.status}</span>
              <p className="result-code">{parcel.code}</p>
              <p>{parcel.origin} → {parcel.destination} · Receiver: {parcel.receiver_name}</p>
            </>
          )}
          <div className="result-stats">
            <div><strong>{result.co2_avoided_kg} kg</strong><span>CO2 avoided</span></div>
            <div><strong>{result.credits_awarded}</strong><span>credits to {parcel ? parcel.sender : "the sender"} ({result.credits_value_eur} EUR)</span></div>
          </div>
          {result.capped && (
            <p className="sub">Daily credit cap reached for this sender, so fewer credits were issued.</p>
          )}
        </div>
      )}
    </div>
  );
}