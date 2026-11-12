from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

import models as m
import seed as seed_module
import services
from database import Base, engine, get_db
from schemas import CollectIn, ParcelIn, QuoteIn, ScanIn
from services import BusinessError


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)  # creates tables if they don't exist yet
    yield


app = FastAPI(title="GreenLink Demo API", lifespan=lifespan)

# Wide open for the demo; tighten to your real frontend URL before sharing widely.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def _get_parcel(db: Session, code: str) -> m.Parcel:
    parcel = db.scalar(select(m.Parcel).where(m.Parcel.code == code.strip().upper()))
    if not parcel:
        raise HTTPException(404, "Parcel not found")
    return parcel


# ---------- reference data ----------

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
    q = select(m.Departure).order_by(m.Departure.departs_at)
    if route_id:
        q = q.where(m.Departure.route_id == route_id)
    if upcoming:
        q = q.where(m.Departure.departs_at > datetime.now(timezone.utc))
    rows = db.scalars(q.limit(limit)).all()
    return [{**services.departure_dict(d), "route_id": d.route_id} for d in rows]


@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    """Used by the demo role-switcher (no real login in the demo)."""
    rows = db.scalars(select(m.User).order_by(m.User.id)).all()
    return [{"id": u.id, "name": u.name, "role": u.role, "business_name": u.business_name} for u in rows]


# ---------- parcels ----------

@app.get("/parcels")
def list_parcels(sender_id: int | None = None, status: str | None = None, limit: int = 50,
                 db: Session = Depends(get_db)):
    q = select(m.Parcel).order_by(m.Parcel.created_at.desc())
    if sender_id:
        q = q.where(m.Parcel.sender_id == sender_id)
    if status:
        q = q.where(m.Parcel.status == status)
    rows = db.scalars(q.limit(limit)).all()
    return [services.parcel_to_dict(p, with_events=False) for p in rows]


@app.post("/parcels/quote")
def quote_parcel(body: QuoteIn, db: Session = Depends(get_db)):
    """Price + best bus + CO2 estimate, WITHOUT creating anything. Used before the sender confirms."""
    return services.quote(db, body.route_id, body.weight_kg)


@app.post("/parcels")
def create_parcel(body: ParcelIn, db: Session = Depends(get_db)):
    parcel = services.create_parcel(db, body)
    db.commit()
    quote = services.quote(db, body.route_id, body.weight_kg)
    return {"parcel": services.parcel_to_dict(parcel), "best_departure": quote["best_departure"],
            "estimated_co2_avoided_kg": quote["estimated_co2_avoided_kg"]}


@app.get("/parcels/{code}")
def get_parcel(code: str, db: Session = Depends(get_db)):
    return services.parcel_to_dict(_get_parcel(db, code))


@app.post("/parcels/{code}/scan")
def scan_parcel(code: str, body: ScanIn | None = None, db: Session = Depends(get_db)):
    """One scan moves the parcel to its next step (drop-off -> matched -> loaded -> in transit -> arrived)."""
    parcel = _get_parcel(db, code)
    result = services.advance_parcel(db, parcel, body.actor_id if body else None)
    db.commit()
    return {**result, "parcel": services.parcel_to_dict(parcel)}


@app.post("/parcels/{code}/collect")
def collect_parcel(code: str, body: CollectIn, db: Session = Depends(get_db)):
    parcel = _get_parcel(db, code)
    result = services.collect_parcel(db, parcel, body.pickup_code)
    db.commit()
    return {**result, "parcel": services.parcel_to_dict(parcel)}


# ---------- dashboards & logs ----------

@app.get("/senders/{sender_id}/summary")
def sender_summary(sender_id: int, db: Session = Depends(get_db)):
    return services.sender_summary(db, sender_id)

@app.get("/senders/{sender_id}/impact")
def sender_impact(sender_id: int, weeks: int = 6, db: Session = Depends(get_db)):
    """Weekly CO2 and credits for the dashboard charts."""
    return services.sender_impact(db, sender_id, weeks)

@app.get("/notifications")
def list_notifications(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.scalars(select(m.Notification).order_by(m.Notification.created_at.desc()).limit(limit)).all()
    return [{"id": n.id, "to": n.recipient_phone, "channel": n.channel, "message": n.message,
             "parcel_id": n.parcel_id, "at": n.created_at} for n in rows]


# ---------- admin ----------

@app.post("/admin/match-pending")
def match_pending(db: Session = Depends(get_db)):
    count = services.match_pending(db)
    db.commit()
    return {"matched": count}


@app.post("/admin/reset-demo")
def reset_demo():
    """Wipes and re-seeds everything. Wire this to a 'Reset demo' button in the admin screen."""
    seed_module.reset_schema()
    return seed_module.seed()
