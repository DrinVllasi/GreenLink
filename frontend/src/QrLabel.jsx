import { QRCodeSVG } from "qrcode.react";

export default function QrLabel({ parcel }) {
  return (
    <div className="label print-area">
      <QRCodeSVG value={parcel.code} size={160} marginSize={2} />
      <div className="label-text">
        <p className="label-code">{parcel.code}</p>
        <p>{parcel.origin} → {parcel.destination}</p>
        <p>{parcel.weight_kg} kg · {parcel.content_type}</p>
        <p>To: {parcel.receiver_name}</p>
        <p>From: {parcel.sender}</p>
      </div>
    </div>
  );
}