// All backend calls live here, so the rest of the app never worries about URLs.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Cannot reach the server. Check your connection and try again.");
  }
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const data = JSON.parse(text);
      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        message = data.detail.map((d) => d.msg).join("; ");
      }
    } catch {
      // not JSON, keep the raw text
    }
    throw new Error(message);
  }
  return res.json();
}

export const getRoutes = () => request("/routes");
export const getDepartures = (limit = 10) => request(`/departures?limit=${limit}`);
export const getParcel = (code) => request(`/parcels/${code}`);
export const getUsers = () => request("/users");
export const getQuote = (body) =>
  request("/parcels/quote", { method: "POST", body: JSON.stringify(body) });

export const createParcel = (body) =>
  request("/parcels", { method: "POST", body: JSON.stringify(body) });
export const getParcels = (senderId) => request(`/parcels?sender_id=${senderId}`);
export const scanParcel = (code) =>
  request(`/parcels/${encodeURIComponent(code)}/scan`, { method: "POST", body: "{}" });
export const collectParcel = (code, pickupCode) =>
  request(`/parcels/${encodeURIComponent(code)}/collect`, {
    method: "POST",
    body: JSON.stringify({ pickup_code: pickupCode }),
  });
export const getSenderSummary = (id) => request(`/senders/${id}/summary`);
export const getSenderImpact = (id, weeks = 6) => request(`/senders/${id}/impact?weeks=${weeks}`);
export function getNotifications(limit = 20) {
  return request(`/notifications?limit=${limit}`);
}

export function getAllParcels(limit = 200) {
  return request(`/parcels?limit=${limit}`);
}
export const getForecastMetrics = () => request("/forecast/metrics");
export const getForecastTable = () => request("/forecast/table");