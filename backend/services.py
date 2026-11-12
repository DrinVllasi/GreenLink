"""Business logic for parcels: quote, create, scan (advance status), collect, summaries."""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import models as m
from co2 import co2_avoided, credits_for, credits_to_eur, max_redeemable
from matching import rank_departures
from pricing import price_for

MAX_WEIGHT_KG = 10.0
DAILY_CREDIT_CAP = 300  # anti-abuse: max credits one sender can earn per day (UTC)
ALLOWED_CONTENT = ["documents", "spare parts", "handmade goods", "food products", "online order", "other"]


class BusinessError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def utcnow():
    return datetime.now(timezone.utc)


# ---------- small helpers ----------

def size_for(weight: float) -> str:
    return "S" if weight < 2 else "M" if weight < 5 else "L"


def _check_weight(weight_kg: float):
    if weight_kg <= 0 or weight_kg > MAX_WEIGHT_KG:
        raise BusinessError(f"Weight must be between 0 and {MAX_WEIGHT_KG:g} kg", 422)


def _event(db: Session, parcel: m.Parcel, status: str, actor_id=None, note=None):
    db.add(m.ParcelEvent(parcel_id=parcel.id, status=status, actor_id=actor_id, note=note, created_at=utcnow()))


def _notify(db: Session, parcel: m.Parcel, phone: str | None, message: str):
    """Simulated SMS/Viber/WhatsApp: just stored, and shown in an in-app log."""
    db.add(m.Notification(parcel_id=parcel.id, recipient_phone=phone or "-", channel="sms",
                          message=message, created_at=utcnow()))


def _new_code(db: Session) -> str:
    while True:
        code = "GL-" + "".join(random.choices("0123456789", k=6))
        if not db.scalar(select(m.Parcel.id).where(m.Parcel.code == code)):
            return code


def _route_for(db: Session, origin_id: int, destination_id: int) -> m.Route:
    route = db.scalar(select(m.Route).where(m.Route.origin_id == origin_id,
                                            m.Route.destination_id == destination_id))
    if not route:
        raise BusinessError("Route not found", 404)
    return route

def credit_balance(db: Session, user_id: int) -> int:
    return int(db.scalar(
        select(func.coalesce(func.sum(m.CreditEntry.credits), 0)).where(m.CreditEntry.user_id == user_id)
    ))


def redemption_info(db: Session, parcel: m.Parcel) -> dict:
    used = int(db.scalar(
        select(func.coalesce(func.sum(-m.CreditEntry.credits), 0))
        .where(m.CreditEntry.parcel_id == parcel.id, m.CreditEntry.entry_type == "redeem")
    ))
    return {"credits_used": used, "discount_eur": credits_to_eur(used)}

def _candidates(db: Session, route_id: int, after: datetime):
    q = (select(m.Departure)
         .where(m.Departure.route_id == route_id, m.Departure.departs_at > after)
         .order_by(m.Departure.departs_at).limit(60))
    return db.scalars(q).all()


def departure_dict(d: m.Departure) -> dict:
    return {
        "id": d.id, "operator": d.operator.name,
        "origin": d.route.origin.city, "destination": d.route.destination.city,
        "departs_at": d.departs_at, "arrives_at": d.arrives_at,
        "capacity_kg": d.capacity_kg, "booked_kg": round(d.booked_kg, 1),
        "free_kg": round(d.capacity_kg - d.booked_kg, 1),
    }


def _ranked_dict(r: dict) -> dict:
    return {**departure_dict(r["departure"]), "score": round(r["score"], 2), "reasons": r["reasons"]}


def parcel_to_dict(p: m.Parcel, with_events: bool = True) -> dict:
    data = {
        "code": p.code, "status": p.status, "weight_kg": p.weight_kg, "size": p.size,
        "content_type": p.content_type, "price": p.price,
        "origin": p.origin.city, "destination": p.destination.city,
        "sender": p.sender.business_name or p.sender.name,
        "receiver_name": p.receiver_name, "receiver_phone": p.receiver_phone,
        "pickup_code": p.pickup_code,  # demo only: in production the receiver gets this by SMS
        "created_at": p.created_at, "delivered_at": p.delivered_at,
        "departure": departure_dict(p.departure) if p.departure else None,
    }
    if with_events:
        data["events"] = [{"status": e.status, "at": e.created_at, "note": e.note} for e in p.events]
    return data


# ---------- quote & create ----------

def quote(db: Session, route_id: int, weight_kg: float, sender_id: int | None = None) -> dict:
    route = db.get(m.Route, route_id)
    if not route:
        raise BusinessError("Route not found", 404)
    _check_weight(weight_kg)
    now = utcnow()
    ranked = rank_departures(_candidates(db, route.id, now), weight_kg, now)
    co2 = co2_avoided(route.distance_km, weight_kg)
    price = price_for(route.distance_km, weight_kg)
    result = {
        "route": {"id": route.id, "origin": route.origin.city, "destination": route.destination.city,
                  "distance_km": route.distance_km},
        "price": price,
        "estimated_co2_avoided_kg": co2,
        "estimated_credits": credits_for(co2),
        "best_departure": _ranked_dict(ranked[0]) if ranked else None,
        "alternatives": [_ranked_dict(r) for r in ranked[1:3]],
    }
    if sender_id:
        balance = credit_balance(db, sender_id)
        used, discount = max_redeemable(price, balance)
        result.update({"credits_balance": balance, "redeemable_credits": used,
                       "discount_eur": discount, "price_after_credits": round(price - discount, 2)})
    return result


def create_parcel(db: Session, data) -> m.Parcel:
    sender = db.get(m.User, data.sender_id)
    if not sender or sender.role != "sender":
        raise BusinessError("Sender not found", 404)
    route = db.get(m.Route, data.route_id)
    if not route:
        raise BusinessError("Route not found", 404)
    _check_weight(data.weight_kg)
    content = data.content_type.strip().lower()
    if content not in ALLOWED_CONTENT:
        raise BusinessError(f"Content type not allowed. Allowed: {', '.join(ALLOWED_CONTENT)}", 422)

    weight = round(data.weight_kg, 1)
    full_price = price_for(route.distance_km, weight)
    used, discount = 0, 0.0
    if data.use_credits:
        used, discount = max_redeemable(full_price, credit_balance(db, sender.id))
    parcel = m.Parcel(
        code=_new_code(db), sender_id=sender.id,
        receiver_name=data.receiver_name.strip(), receiver_phone=data.receiver_phone.strip(),
        origin_id=route.origin_id, destination_id=route.destination_id,
        weight_kg=weight, size=size_for(weight), content_type=content,
        price=round(full_price - discount, 2), status="booked",
        pickup_code=f"{random.randint(0, 9999):04d}", created_at=utcnow(),
    )
    db.add(parcel)
    db.flush()
    note = f"Used {used} credits (-{discount:.2f} EUR)" if used else None
    _event(db, parcel, "booked", sender.id, note)
    if used:
        db.add(m.CreditEntry(user_id=sender.id, parcel_id=parcel.id, entry_type="redeem",
                             co2_avoided_kg=0, credits=-used, created_at=utcnow()))
    _notify(db, parcel, sender.phone,
            f"GreenLink: parcel {parcel.code} booked ({route.origin.city} to {route.destination.city}). "
            f"Drop it at the {route.origin.city} station box.")
    return parcel


# ---------- matching & scanning ----------

def match_parcel(db: Session, parcel: m.Parcel):
    """Try to assign the parcel to the best departure. Returns the ranked result or None."""
    route = _route_for(db, parcel.origin_id, parcel.destination_id)
    now = utcnow()
    ranked = rank_departures(_candidates(db, route.id, now), parcel.weight_kg, now)
    if not ranked:
        return None
    best = ranked[0]
    best["departure"].booked_kg += parcel.weight_kg
    parcel.departure_id = best["departure"].id
    return best


def _set_matched(db: Session, parcel: m.Parcel, result: dict, actor_id=None):
    parcel.status = "matched"
    _event(db, parcel, "matched", None,
           "Matched to " + result["departure"].operator.name + ": " + "; ".join(result["reasons"]))


def advance_parcel(db: Session, parcel: m.Parcel, actor_id=None) -> dict:
    """One scan = move the parcel to its next step. Returns a short message about what happened."""
    status = parcel.status
    order = m.PARCEL_STATUSES

    if status == "collected":
        raise BusinessError("Parcel already collected", 409)
    if status == "arrived":
        raise BusinessError("Parcel has arrived - the receiver must collect it with the pickup code", 409)

    if status == "booked":
        parcel.status = "dropped_off"
        _event(db, parcel, "dropped_off", actor_id, "Scanned in at the origin box")
        result = match_parcel(db, parcel)
        if result:
            _set_matched(db, parcel, result, actor_id)
            return {"message": "Dropped off and matched to a bus", "matched": True}
        return {"message": "Dropped off, but no bus has free space yet - will retry", "matched": False}

    if status == "dropped_off":  # was waiting for capacity
        result = match_parcel(db, parcel)
        if not result:
            raise BusinessError("Still no bus with enough free space", 409)
        _set_matched(db, parcel, result, actor_id)
        return {"message": "Matched to a bus", "matched": True}

    nxt = order[order.index(status) + 1]
    parcel.status = nxt
    _event(db, parcel, nxt, actor_id)
    if nxt == "arrived":
        _notify(db, parcel, parcel.receiver_phone,
                f"GreenLink: your parcel {parcel.code} has arrived at {parcel.destination.city} station. "
                f"Pickup code: {parcel.pickup_code}")
    return {"message": f"Status is now '{nxt}'", "matched": True}


def match_pending(db: Session) -> int:
    """Retry matching for parcels that were dropped off but found no space. Returns how many got matched."""
    count = 0
    for parcel in db.scalars(select(m.Parcel).where(m.Parcel.status == "dropped_off")).all():
        result = match_parcel(db, parcel)
        if result:
            _set_matched(db, parcel, result)
            count += 1
    return count


# ---------- pickup & credits ----------

def collect_parcel(db: Session, parcel: m.Parcel, pickup_code: str) -> dict:
    if parcel.status == "collected":
        raise BusinessError("Parcel already collected", 409)
    if parcel.status != "arrived":
        raise BusinessError(f"Parcel is '{parcel.status}' - not ready for pickup yet", 409)
    if pickup_code.strip() != parcel.pickup_code:
        raise BusinessError("Wrong pickup code", 403)

    route = _route_for(db, parcel.origin_id, parcel.destination_id)
    now = utcnow()
    co2 = co2_avoided(route.distance_km, parcel.weight_kg)
    wanted = credits_for(co2)

    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    earned_today = db.scalar(
        select(func.coalesce(func.sum(m.CreditEntry.credits), 0))
        .where(m.CreditEntry.user_id == parcel.sender_id,
               m.CreditEntry.entry_type == "earn",
               m.CreditEntry.created_at >= start_of_day)
    )
    awarded = max(min(wanted, DAILY_CREDIT_CAP - earned_today), 0)

    parcel.status = "collected"
    parcel.delivered_at = now
    db.add(m.CreditEntry(user_id=parcel.sender_id, parcel_id=parcel.id, entry_type="earn",
                         co2_avoided_kg=co2, credits=awarded, created_at=now))
    _event(db, parcel, "collected", None, f"Receiver confirmed with pickup code. {awarded} credits issued.")
    _notify(db, parcel, parcel.sender.phone,
            f"GreenLink: parcel {parcel.code} delivered. You avoided {co2} kg CO2 and earned {awarded} credits.")

    return {
        "co2_avoided_kg": co2, "credits_awarded": awarded,
        "credits_value_eur": credits_to_eur(awarded),
        "capped": awarded < wanted,
    }


def sender_summary(db: Session, sender_id: int) -> dict:
    sender = db.get(m.User, sender_id)
    if not sender or sender.role != "sender":
        raise BusinessError("Sender not found", 404)

    count, spent = db.execute(
        select(func.count(m.Parcel.id), func.coalesce(func.sum(m.Parcel.price), 0))
        .where(m.Parcel.sender_id == sender_id)
    ).one()
    in_progress = db.scalar(
        select(func.count(m.Parcel.id))
        .where(m.Parcel.sender_id == sender_id, m.Parcel.status != "collected")
    )
    co2, balance = db.execute(
        select(func.coalesce(func.sum(m.CreditEntry.co2_avoided_kg), 0),
               func.coalesce(func.sum(m.CreditEntry.credits), 0))
        .where(m.CreditEntry.user_id == sender_id)
    ).one()

    return {
        "sender": sender.business_name or sender.name,
        "parcels_total": count, "parcels_in_progress": in_progress,
        "total_spent_eur": round(spent, 2),
        "co2_avoided_kg": round(co2, 1),
        "credits_balance": int(balance), "credits_value_eur": credits_to_eur(int(balance)),
    }

def sender_impact(db: Session, sender_id: int, weeks: int = 6) -> dict:
    """CO2 and credits earned per week (Monday-start, UTC), zero-filled, straight from the ledger."""
    sender = db.get(m.User, sender_id)
    if not sender or sender.role != "sender":
        raise BusinessError("Sender not found", 404)
    weeks = max(1, min(weeks, 26))

    today = utcnow().date()
    this_monday = today - timedelta(days=today.weekday())
    first_monday = this_monday - timedelta(weeks=weeks - 1)
    buckets = {
        first_monday + timedelta(weeks=i): {"week_start": (first_monday + timedelta(weeks=i)).isoformat(),
                                            "co2_avoided_kg": 0.0, "credits_earned": 0, "parcels": 0}
        for i in range(weeks)
    }

    start = datetime.combine(first_monday, datetime.min.time(), tzinfo=timezone.utc)
    rows = db.scalars(
        select(m.CreditEntry).where(m.CreditEntry.user_id == sender_id,
                                    m.CreditEntry.entry_type == "earn",
                                    m.CreditEntry.created_at >= start)
    ).all()
    for r in rows:
        day = r.created_at.astimezone(timezone.utc).date()
        bucket = buckets.get(day - timedelta(days=day.weekday()))
        if bucket:
            bucket["co2_avoided_kg"] += r.co2_avoided_kg
            bucket["credits_earned"] += r.credits
            bucket["parcels"] += 1

    for b in buckets.values():
        b["co2_avoided_kg"] = round(b["co2_avoided_kg"], 2)
    return {"sender": sender.business_name or sender.name, "weeks": list(buckets.values())}
