// All backend calls live here, so the rest of the app never worries about URLs.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export const getRoutes = () => request("/routes");
export const getDepartures = (limit = 10) => request(`/departures?limit=${limit}`);
export const getParcel = (code) => request(`/parcels/${code}`);
export const resetDemo = () => request("/admin/reset-demo", { method: "POST" });
export const getUsers = () => request("/users");