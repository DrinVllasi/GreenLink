# GreenLink demo - setup

## 1. Start PostgreSQL (pick ONE)

**A) Docker (easiest):** from this folder run `docker compose up -d`

**B) Installed PostgreSQL:** create a database/user matching `.env.example`:
```sql
CREATE USER greenlink WITH PASSWORD 'greenlink';
CREATE DATABASE greenlink OWNER greenlink;
```

**C) Free hosted Postgres** (Neon, Supabase, Render...): copy its connection string into `.env`.

## 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate 
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
python seed.py              # creates tables + demo data
uvicorn main:app --reload
```

Open http://localhost:8000/docs - try `GET /routes`, `GET /departures`, `POST /admin/reset-demo`.
To see a parcel, copy a `code` (GL-xxxxxx) from the database and use `GET /parcels/{code}`.


<!-- Starting it again another day -->

<!--Open the backend folder, type cmd in the address bar, and press Enter.
Run venv\Scripts\activate.
Run uvicorn main:app --reload. -->