# GreenLink demo

Demo for the Digital Green Innovation Competition 2026.

GreenLink lets Kosovar SMEs send small parcels (under 10 kg) between cities in the luggage space of intercity buses that already run. The sender books a parcel, drops it at the origin station, the system matches it to a bus with free space, staff scan it along the way, and the receiver collects it with a pickup code. The CO2 avoided compared with a dedicated van trip is calculated, and the sender earns green credits that give a discount on future shipments.

> **This is a demo, not a production system.** Prices, SMS, payments, login and the AI training data are simulated.

## Live demo

- App : https://greenlink-ks.vercel.app
- API docs: https://greenlink-api-go5j.onrender.com/docs

The demo runs on free cloud tiers. **The first request can take a couple of minutes** while the server wakes up and trains the forecast model (in testing: 2 to 3 minutes). That is a free-tier trade-off, not an architecture limit. A yellow "Waking up the server..." notice appears if the first load takes more than 4 seconds. Before presenting, open the link and click through one flow about 15 minutes ahead.

## The demo story (end to end)

1. Switch role with the user dropdown (no real login). As a sender, open the dashboard (CO2 avoided, credits, weekly charts).
2. Book a parcel (for example Prishtine to Prizren, 5 kg). The live preview shows the price, the best bus with reasons, the CO2 and credits to earn, and the AI recommendation. Optionally use credits.
3. A QR label is generated (it holds only the parcel code).
4. As Station Agent, scan the parcel 4 times: matched, loaded, in transit, arrived. One scan always means "next step".
5. Hand over with the receiver's pickup code (a wrong code gives a readable error).
6. Back as sender: status collected, credits added, dashboard updated.
7. As Admin: status counts, the AI forecast card (metrics, chart, table) and the simulated SMS log.

### Demo users

| Id | Name | Role |
|----|------|------|
| 1 | Demo Admin | admin |
| 2 | Driver Demo | driver |
| 3 | Station Agent Demo | agent |
| 4 | Artisan Foods Owner | sender |
| 5 | Spare Parts Owner | sender |
| 6 | Boutique Owner | sender |

## Tech stack

- Frontend: React (Vite, JavaScript), qrcode.react, html5-qrcode, Recharts. Hosted on Vercel.
- Backend: FastAPI, SQLAlchemy 2, psycopg v3, scikit-learn (forecast). Hosted on Render.
- Database: PostgreSQL (Neon in the cloud, local PostgreSQL for development).

## How it works

### Parcel lifecycle

`booked -> dropped_off -> matched -> loaded -> in_transit -> arrived -> collected`

- The first scan does the drop-off and the automatic matching. If no bus has space, the parcel stays `dropped_off` and a new scan retries.
- From `arrived`, only the handover (collect) with the pickup code works.
- Every status change is stored as an event, so each parcel has a full audit trail.


### AI part: capacity-matching forecast

- Two small scikit-learn random forests predict, per route, weekday and hour (UTC): the expected bus fill and the expected delay.
- The model is trained at server startup. If training fails or there are fewer than 200 rows, the app falls back to the normal price.
- It is used in two bounded ways:
  - **Dynamic price:** the base price is adjusted by `clamp((expected_fill - 0.55) x 0.5, -15%, +15%)`, rounded to a whole percent.
  - **Ranking nudge:** a small score adjustment (capped at one score point) for expected fill and for expected delay above 10 minutes.
- The model never decides whether a parcel fits, so it cannot overbook a bus.
- Hold-out test: trained on everything older than 14 days, scored on the newest 14 days, compared with "predict the average". Latest result: fill error 5.8 points vs 11.2 for the baseline; delay error 2.6 min vs 4.1 min.
- **The training data is simulated** (with built-in patterns), so these numbers show that the pipeline works, not real-world accuracy. In production the same pipeline would learn from real scan history. The UI labels it "trained on simulated demo data".
- There is no chatbot and no LLM.

### CO2 and credits (formula, not AI)

Pilot assumptions, in `backend/co2.py`:

- A dedicated van emits 0.225 kg CO2/km; a dedicated trip is round-trip and shared by about 10 parcels.
- A parcel on a bus adds a marginal 0.0003 kg CO2 per kg-km.
- 10 credits per kg CO2 avoided; 1 credit = 0.008 EUR (roughly the EU carbon price, about 80 EUR per tonne).
- Credits can pay at most 25% of a parcel.
- Credits are issued only after the receiver confirms with the pickup code (capped at 300 credits per sender per day) and are stored in an auditable ledger. They are platform credits, not tradable offsets.

Example: 5 kg Prishtine to Prizren avoids about 3.59 kg CO2 and earns 36 credits.

### Pricing

Base price (placeholder): `1.00 + 0.03 EUR/km + 0.20 EUR/kg`, then the AI adjustment (at most +/-15%), then credits (at most 25% off). In the worst case the sender pays about 64% of the base price. **These are demo numbers, not a cost model.** There is no cost data yet, and the margin still has to be agreed.

## What is simulated

- SMS/Viber/WhatsApp: messages are stored in a notifications table and shown in the admin view (nothing is sent). Booking and credit messages go to the sender; the pickup code goes to the receiver.
- Payments: mock.
- Login: role switcher instead of real authentication.
- Bus timetables, capacities, operators, past parcels, fill and delay history: generated by `seed.py`.
- Offline scanning is on the production roadmap and is not part of the demo (a manual code field covers a failing camera).

## Run locally

Requirements: Python (developed on 3.14), Node.js, PostgreSQL.

### 1. Start PostgreSQL

**Installed PostgreSQL:** create a user and database matching `backend/.env.example`:

```sql
CREATE USER greenlink WITH PASSWORD 'greenlink';
CREATE DATABASE greenlink OWNER greenlink;
```

**Free hosted Postgres** (Neon, Supabase, Render...): copy its connection string into `backend/.env`.

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
python seed.py              # creates tables + demo data
uvicorn main:app --reload
```

For a local database, `.env` contains:

```
DATABASE_URL=postgresql+psycopg://greenlink:greenlink@localhost:5432/greenlink
```

Open http://localhost:8000/docs and try `GET /routes`, `GET /departures` and `GET /forecast/metrics`. To see a parcel, call `GET /parcels`, copy a `code` (GL-xxxxxx) and use `GET /parcels/{code}`.

### 3. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The frontend reads the API address from `VITE_API_URL` (set it for the deployed build; check `frontend/src/api.js` for the local default).

### Starting it again another day

1. Backend: open the `backend` folder, type `cmd` in the address bar and press Enter. Run `venv\Scripts\activate`, then `uvicorn main:app --reload`.
2. Frontend: open the `frontend` folder, type `cmd` in the address bar and press Enter. Run `npm run dev`.
3. To get clean demo data, run `python seed.py` in the backend window (venv active) before starting the server.

### Tests

With the server running, in a second terminal with the venv active: `python smoke_test.py` (all checks should say PASS). `python forecast.py` prints the model metrics and two sample forecasts.

## Seed data and reseeding

`seed.py` wipes and recreates the demo data: 6 routes (3 city pairs, both directions), 3 fake bus operators, 1632 departures (from 60 days in the past to 7 days ahead of the seed date), 6 users, 40 completed past parcels and 4 live parcels. Because buses only run for 7 days after seeding, **reseed the day before or the morning of presenting**. After reseeding the live database, the server may need up to a minute to retrain the model. Check `/forecast/metrics` shows `ready: true`.

## API overview

Main endpoints (full list and request bodies in `/docs`):

- `GET /health`, `/routes`, `/departures`, `/users`, `/parcels`, `/parcels/{code}`, `/notifications`
- `GET /senders/{id}/summary`, `/senders/{id}/impact`
- `GET /forecast/metrics`, `/forecast/table`
- `POST /parcels/quote`, `/parcels`, `/parcels/{code}/scan`, `/parcels/{code}/collect`
- `POST /admin/match-pending`

`POST /admin/reset-demo` exists but is disabled (returns 403) unless the environment variable `ALLOW_RESET=1` is set, which is never done on the live server.

## Known limitations

- Free-tier cold start (up to a couple of minutes on the first request); Render's free tier has limited memory, so watch for restarts.
- The pickup code is exposed in API responses and CORS is open (demo only).
- Distances for Gjilan (47 km) and Ferizaj (40 km) are approximate and still to be verified. Prishtine to Prizren (82.6 km) comes from the concept document.
- The sender dashboard can look stale after another role changes data; switching user or refreshing fixes it.
- The base price and margin are placeholders, and the CO2 result rests on the assumption that a van trip is shared by about 10 parcels.
- Times are stored in UTC and shown in the viewer's local time. The forecast works in UTC weekday and hour.

## Repository layout

```
backend/    FastAPI app: main.py, models.py, seed.py, co2.py, pricing.py,
            matching.py, forecast.py, schemas.py, services.py, smoke_test.py
frontend/   React app (src/): App.jsx, api.js, SenderScreen.jsx, ScanScreen.jsx,
            PickupScreen.jsx, SenderDashboard.jsx, ParcelHistory.jsx,
            AdminView.jsx, QrLabel.jsx
```