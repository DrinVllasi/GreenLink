from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

import models as m
import seed as seed_module
from database import Base, engine, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)  # creates tables if they don't exist yet
    yield


app = FastAPI(title="GreenLink Demo API", lifespan=lifespan)

# Wide open for the demo; tighten to your real frontend URL before sharing widely.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/routes")
def list_routes(db: Session = Depends(get_db)):
    rows = db.scalars(select(m.Route)).all()
    return [
        {"id": r.id, "origin": r.origin.city, "destination": r.destination.city, "distance_km": r.distance_km}
        for r in rows
    ]


@app.get("/departures")
def list_departures(route_id: int | None = None, upcoming: bool = True, limit: int = 50,
                    db: Session = Depends(get_db)):
    from datetime import datetime, timezone

    q = select(m.Departure).order_by(m.Departure.departs_at)
    if route_id:
        q = q.where(m.Departure.route_id == route_id)
    if upcoming:
        q = q.where(m.Departure.departs_at > datetime.now(timezone.utc))
    rows = db.scalars(q.limit(limit)).all()
    return [
        {
            "id": d.id, "route_id": d.route_id,
            "origin": d.route.origin.city, "destination": d.route.destination.city,
            "operator": d.operator.name, "departs_at": d.departs_at, "arrives_at": d.arrives_at,
            "capacity_kg": d.capacity_kg, "booked_kg": round(d.booked_kg, 1),
            "free_kg": round(d.capacity_kg - d.booked_kg, 1),
        }
        for d in rows
    ]


@app.get("/parcels/{code}")
def get_parcel(code: str, db: Session = Depends(get_db)):
    p = db.scalar(select(m.Parcel).where(m.Parcel.code == code))
    if not p:
        raise HTTPException(404, "Parcel not found")
    return {
        "code": p.code, "status": p.status, "weight_kg": p.weight_kg, "size": p.size, "price": p.price,
        "origin": p.origin.city, "destination": p.destination.city,
        "receiver_name": p.receiver_name, "created_at": p.created_at, "delivered_at": p.delivered_at,
        "events": [{"status": e.status, "at": e.created_at, "note": e.note} for e in p.events],
    }


@app.post("/admin/reset-demo")
def reset_demo():
    """Wipes and re-seeds everything. Wire this to a 'Reset demo' button in the admin screen."""
    seed_module.reset_schema()
    return seed_module.seed()
