import { useEffect, useState } from "react";
import { getQuote, createParcel } from "./api";
import QrLabel from "./QrLabel";

const CONTENT_TYPES = [
  "documents", "spare parts", "handmade goods",
  "food products", "online order", "other",
];

function formatTime(iso) {
  return new Date(iso).toLocaleString("en-GB", {
    weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export default function SenderScreen({ user, routes, onBooked }) {
  const [routeId, setRouteId] = useState("");
  const [weight, setWeight] = useState(5);
  const [contentType, setContentType] = useState(CONTENT_TYPES[0]);
  const [receiverName, setReceiverName] = useState("");
  const [receiverPhone, setReceiverPhone] = useState("");
  const [quote, setQuote] = useState(null);
  const [quoteError, setQuoteError] = useState(null);
  const [formError, setFormError] = useState(null);
  const [booked, setBooked] = useState(null);
  const [busy, setBusy] = useState(false);
  const [useCredits, setUseCredits] = useState(false);
  const [quoteVersion, setQuoteVersion] = useState(0);

  // pick the first route once routes have loaded
  useEffect(() => {
    if (!routeId && routes.length > 0) setRouteId(String(routes[0].id));
  }, [routes, routeId]);

  // live quote: runs 0.4 s after the route or weight changes
  useEffect(() => {
    if (!routeId || !(Number(weight) > 0)) {
      setQuote(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      getQuote({ route_id: Number(routeId), weight_kg: Number(weight), sender_id: user.id })
        .then((q) => {
          if (!cancelled) { setQuote(q); setQuoteError(null); }
        })
        .catch((e) => {
          if (!cancelled) { setQuote(null); setQuoteError(e.message); }
        });
    }, 400);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [routeId, weight, user.id, quoteVersion]);

  async function handleBook() {
    setFormError(null);
    if (!receiverName.trim() || !receiverPhone.trim()) {
      setFormError("Please fill in the receiver name and phone.");
      return;
    }
    setBusy(true);
    try {
      const parcel = await createParcel({
        sender_id: user.id,
        route_id: Number(routeId),
        receiver_name: receiverName.trim(),
        receiver_phone: receiverPhone.trim(),
        weight_kg: Number(weight),
        content_type: contentType,
        use_credits: useCredits && !!quote && quote.redeemable_credits > 0,
      });
      setBooked({
        ...(parcel.parcel || parcel),
        credits_used: parcel.credits_used || 0,
        discount_eur: parcel.discount_eur || 0,
      });
      if (onBooked) onBooked();
    } catch (e) {
      setFormError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function bookAnother() {
    setBooked(null);
    setReceiverName("");
    setReceiverPhone("");
    setUseCredits(false);
    setQuoteVersion((v) => v + 1); // re-fetch the quote so the new balance shows
  }

  if (booked) {
    return (
      <div className="card">
        <h2>Parcel booked</h2>
        <p>Parcel code: <strong>{booked.code}</strong></p>
        <p>Pickup code for the receiver: <strong>{booked.pickup_code}</strong></p>
        <p>Price: {booked.price} EUR · Status: {booked.status}</p>
        {booked.credits_used > 0 && (
          <p>Green credits used: <strong>{booked.credits_used}</strong> (-{booked.discount_eur.toFixed(2)} EUR)</p>
        )}
        <QrLabel parcel={booked} />
        <p className="sub">Print the label, stick it on the parcel and drop it at the origin station box.</p>
        <button onClick={() => window.print()}>Print label</button>{" "}
        <button onClick={bookAnother}>Book another parcel</button>
      </div>
    );
  }

  const best = quote && quote.best_departure;
  const canUse = !!quote && quote.redeemable_credits > 0;

  return (
    <div className="card">
      <h2>Send a parcel</h2>
      <p className="sub">Sending as {user.business_name || user.name}</p>

      <div className="form-grid">
        <label>Route
          <select value={routeId} onChange={(e) => setRouteId(e.target.value)}>
            {routes.map((r) => (
              <option key={r.id} value={r.id}>{r.origin} → {r.destination}</option>
            ))}
          </select>
        </label>
        <label>Weight (kg)
          <input type="number" min="0.1" max="10" step="0.1"
            value={weight} onChange={(e) => setWeight(e.target.value)} />
        </label>
        <label>Content type
          <select value={contentType} onChange={(e) => setContentType(e.target.value)}>
            {CONTENT_TYPES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>Receiver name
          <input value={receiverName} onChange={(e) => setReceiverName(e.target.value)} />
        </label>
        <label>Receiver phone
          <input value={receiverPhone} onChange={(e) => setReceiverPhone(e.target.value)}
            placeholder="+383..." />
        </label>
      </div>

      <div className="quote-box">
        <h3>Live preview</h3>
        {quoteError && <p className="error">{quoteError}</p>}
        {!quote && !quoteError && <p className="sub">Enter a weight to see the price.</p>}
        {quote && (
          <>
            <p>Price: <strong>{quote.price} EUR</strong>
              {useCredits && canUse && (
                <> → <strong>{quote.price_after_credits} EUR</strong> with credits</>
              )}
            </p>
            {quote.credits_balance !== undefined && (
              <p>
                <label>
                  <input type="checkbox" checked={useCredits && canUse} disabled={!canUse}
                    onChange={(e) => setUseCredits(e.target.checked)} />{" "}
                  Use my green credits
                  {canUse
                    ? `: ${quote.redeemable_credits} credits = -${quote.discount_eur.toFixed(2)} EUR`
                    : " (none available)"}
                </label>
                <br /><span className="sub">
                  Balance: {quote.credits_balance} credits. Credits can pay at most 25% of a parcel.
                </span>
              </p>
            )}
            <p>CO2 avoided: <strong>{quote.estimated_co2_avoided_kg} kg</strong> ·
              Credits you earn after delivery: <strong>{quote.estimated_credits}</strong></p>
            {best ? (
              <p>
                Best bus: <strong>{best.operator}</strong>, departs {formatTime(best.departs_at)}
                {" "}({best.free_kg} kg free)
                <br /><span className="sub">{best.reasons.join(" · ")}</span>
              </p>
            ) : (
              <p className="error">No bus with free space right now.</p>
            )}
          </>
        )}
      </div>

      {formError && <p className="error">{formError}</p>}
      <button onClick={handleBook} disabled={busy || !quote}>
        {busy ? "Booking..." : "Book parcel"}
      </button>
    </div>
  );
}