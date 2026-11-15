from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select

import models as m
from database import SessionLocal

with SessionLocal() as db:
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(m.Departure).where(m.Departure.route_id == 1, m.Departure.departs_at < now)).all()
    acc = defaultdict(list)
    for d in rows:
        t = d.departs_at.astimezone(timezone.utc)
        acc[(t.weekday(), t.hour)].append(d.booked_kg / d.capacity_kg)
    for label, key in [("Fri 07:00", (4, 7)), ("Sun 10:00", (6, 10))]:
        v = acc[key]
        print(label, f"{sum(v) / len(v):.0%}", f"({len(v)} buses)")