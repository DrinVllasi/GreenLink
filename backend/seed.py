"""Fills the database with demo data. Run:  python seed.py   (it WIPES and recreates everything).

Past departures get SIMULATED load and delay with patterns (weekday, hour, route), so the
forecasting model has something to learn. This is demo data, not real scan history."""
import random
from datetime import datetime, timedelta, timezone

import models as m
from co2 import co2_avoided, credits_for
from database import Base, SessionLocal, engine
from pricing import price_for

# Distances: Prishtine-Prizren comes from the concept doc; the other two are approximate road
# distances - double-check them before the final demo.
ROUTE_PAIRS = [
    ("Prishtinë", "Prizren", 82.6),
    ("Prishtinë", "Gjilan", 47.0),
    ("Prishtinë", "Ferizaj", 40.0),
]
DEPARTURE_HOURS = [7, 10, 14, 17]
DAYS_BACK = 60
DAYS_AHEAD = 7
CONTENT_TYPES = ["documents", "spare parts", "handmade goods", "food products", "online order"]
RECEIVERS = [
    ("Arben K.", "+38344000101"), ("Vjosa M.", "+38344000102"), ("Besnik H.", "+38344000103"),
    ("Drita S.", "+38344000104"), ("Lirim B.", "+38344000105"), ("Era T.", "+38344000106"),
]

# --- simulated demand patterns (the "hidden truth" the model will try to learn) ---
BASE_FILL = 0.45
HOUR_FACTOR = {7: 1.25, 10: 0.80, 14: 0.85, 17: 1.15}             # morning and evening rush fuller
WEEKDAY_FACTOR = [1.10, 1.00, 0.95, 1.00, 1.20, 0.90, 0.70]       # Mon..Sun: Friday fullest, Sunday emptiest
ROUTE_FACTOR = [1.10, 0.90, 0.85]                                 # per city pair: Prizren busiest
DIRECTION_BOOST = 1.15  # from Prishtine in the morning, back to Prishtine in the afternoon


def simulated_fill(pair_index, outbound, weekday, hour):
    """Fraction of the bus's luggage space that ends up booked (0.05 to 0.98)."""
    fill = BASE_FILL * HOUR_FACTOR[hour] * WEEKDAY_FACTOR[weekday] * ROUTE_FACTOR[pair_index]
    if (outbound and hour in (7, 10)) or (not outbound and hour in (14, 17)):
        fill *= DIRECTION_BOOST
    fill += random.gauss(0, 0.07)  # noise, so the model is not learning a perfect formula
    return max(0.05, min(0.98, fill))


def simulated_delay(distance_km, weekday, hour):
    """Minutes late: rush hour, Fridays and longer routes run later; rare big spikes."""
    delay = random.gauss(3, 2) + distance_km / 82.6 * 4
    if hour in (7, 17):
        delay += 6
    if weekday == 4:
        delay += 4
    if random.random() < 1 / 15:
        delay = random.randint(15, 35)
    return max(0, min(45, round(delay)))


def reset_schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def size_for(weight):
    return "S" if weight < 2 else "M" if weight < 5 else "L"


def new_code(used):
    while True:
        code = "GL-" + "".join(random.choices("0123456789", k=6))
        if code not in used:
            used.add(code)
            return code


def add_event(db, parcel, status, when, actor=None, note=None):
    db.add(m.ParcelEvent(parcel_id=parcel.id, status=status, actor_id=actor.id if actor else None,
                         note=note, created_at=when))


def seed():
    random.seed(42)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    used_codes = set()

    with SessionLocal() as db:
        # --- people ---
        users = {
            "admin": m.User(name="Demo Admin", email="admin@greenlink.demo", role="admin"),
            "driver": m.User(name="Driver Demo", email="driver@greenlink.demo", role="driver", phone="+38344000201"),
            "agent": m.User(name="Station Agent Demo", email="agent@greenlink.demo", role="agent", phone="+38344000202"),
        }
        senders = [
            m.User(name="Artisan Foods Owner", email="artisan@greenlink.demo", role="sender",
                   business_name="Demo Artisan Foods", phone="+38344000301"),
            m.User(name="Spare Parts Owner", email="parts@greenlink.demo", role="sender",
                   business_name="Demo Spare Parts", phone="+38344000302"),
            m.User(name="Boutique Owner", email="boutique@greenlink.demo", role="sender",
                   business_name="Demo Online Boutique", phone="+38344000303"),
        ]
        db.add_all(list(users.values()) + senders)

        operators = [m.Operator(name=f"Demo Bus Co. {i}") for i in (1, 2, 3)]
        db.add_all(operators)

        # --- stations & routes (both directions) ---
        stations = {}
        for a, b, _ in ROUTE_PAIRS:
            for city in (a, b):
                if city not in stations:
                    stations[city] = m.Station(name=f"{city} Bus Station", city=city)
        db.add_all(stations.values())
        db.flush()

        routes = []
        for a, b, km in ROUTE_PAIRS:
            routes.append(m.Route(origin_id=stations[a].id, destination_id=stations[b].id, distance_km=km))
            routes.append(m.Route(origin_id=stations[b].id, destination_id=stations[a].id, distance_km=km))
        db.add_all(routes)
        db.flush()

        # route id -> (city pair index, True if it leaves Prishtine). Routes were added in pairs.
        route_meta = {r.id: (i // 2, i % 2 == 0) for i, r in enumerate(routes)}

        # --- departures: past ones get simulated load + delay, future ones start empty ---
        departures = []
        for day in range(-DAYS_BACK, DAYS_AHEAD + 1):
            for route in routes:
                pair_index, outbound = route_meta[route.id]
                for i, hour in enumerate(DEPARTURE_HOURS):
                    departs = (now + timedelta(days=day)).replace(hour=hour, minute=0)
                    minutes = int(route.distance_km / 45 * 60) + 10
                    capacity = random.choice([40, 60, 80])
                    is_past = departs < now
                    if is_past:
                        fill = simulated_fill(pair_index, outbound, departs.weekday(), hour)
                        booked = round(capacity * fill, 1)
                        delay = simulated_delay(route.distance_km, departs.weekday(), hour)
                    else:
                        booked, delay = 0, None
                    departures.append(m.Departure(
                        route_id=route.id,
                        operator_id=operators[(route.id + i) % 3].id,
                        departs_at=departs,
                        arrives_at=departs + timedelta(minutes=minutes),
                        capacity_kg=capacity,
                        booked_kg=booked,
                        delay_min=delay,
                    ))
        # Send departures in batches of 100: one giant INSERT made Neon drop the connection
        for i in range(0, len(departures), 100):
            db.add_all(departures[i:i + 100])
            db.flush()
        route_by_id = {r.id: r for r in routes}

        # --- ~40 past, completed parcels (so dashboards look alive) ---
        past = [d for d in departures if d.departs_at < now - timedelta(hours=6)]
        for dep in random.sample(past, 40):
            route = route_by_id[dep.route_id]
            sender = random.choice(senders)
            rname, rphone = random.choice(RECEIVERS)
            weight = round(random.uniform(0.5, 9.0), 1)
            created = dep.departs_at - timedelta(hours=random.randint(3, 20))
            collected = dep.arrives_at + timedelta(minutes=random.randint(30, 180))
            parcel = m.Parcel(
                code=new_code(used_codes), sender_id=sender.id, receiver_name=rname, receiver_phone=rphone,
                origin_id=route.origin_id, destination_id=route.destination_id, weight_kg=weight,
                size=size_for(weight), content_type=random.choice(CONTENT_TYPES),
                price=price_for(route.distance_km, weight), status="collected", departure_id=dep.id,
                pickup_code=f"{random.randint(0, 9999):04d}", created_at=created, delivered_at=collected,
            )
            db.add(parcel)
            db.flush()
            # the simulated load already represents past traffic; just make sure it covers this parcel
            dep.booked_kg = max(dep.booked_kg, weight)
            add_event(db, parcel, "booked", created, sender)
            add_event(db, parcel, "dropped_off", created + timedelta(minutes=20), users["agent"])
            add_event(db, parcel, "matched", created + timedelta(minutes=21), None, "Auto-matched to departure")
            add_event(db, parcel, "loaded", dep.departs_at - timedelta(minutes=10), users["driver"])
            add_event(db, parcel, "in_transit", dep.departs_at, users["driver"])
            add_event(db, parcel, "arrived", dep.arrives_at, users["agent"])
            add_event(db, parcel, "collected", collected, None, "Receiver confirmed with pickup code")
            co2 = co2_avoided(route.distance_km, weight)
            db.add(m.CreditEntry(user_id=sender.id, parcel_id=parcel.id, entry_type="earn",
                                 co2_avoided_kg=co2, credits=credits_for(co2), created_at=collected))

        # --- a few live parcels in different states ---
        upcoming = sorted([d for d in departures if now < d.departs_at < now + timedelta(days=1)],
                          key=lambda d: d.departs_at)
        live_statuses = ["booked", "dropped_off", "matched", "matched"]
        for status in live_statuses:
            dep = random.choice(upcoming)
            route = route_by_id[dep.route_id]
            sender = random.choice(senders)
            rname, rphone = random.choice(RECEIVERS)
            weight = round(random.uniform(0.5, 6.0), 1)
            has_departure = status == "matched"
            parcel = m.Parcel(
                code=new_code(used_codes), sender_id=sender.id, receiver_name=rname, receiver_phone=rphone,
                origin_id=route.origin_id, destination_id=route.destination_id, weight_kg=weight,
                size=size_for(weight), content_type=random.choice(CONTENT_TYPES),
                price=price_for(route.distance_km, weight), status=status,
                departure_id=dep.id if has_departure else None,
                pickup_code=f"{random.randint(0, 9999):04d}", created_at=now - timedelta(hours=1),
            )
            db.add(parcel)
            db.flush()
            add_event(db, parcel, "booked", now - timedelta(hours=1), sender)
            if status in ("dropped_off", "matched"):
                add_event(db, parcel, "dropped_off", now - timedelta(minutes=40), users["agent"])
            if has_departure:
                dep.booked_kg += weight
                add_event(db, parcel, "matched", now - timedelta(minutes=39), None, "Auto-matched to departure")

        db.commit()
        return {
            "users": len(users) + len(senders), "routes": len(routes),
            "departures": len(departures), "parcels": 40 + len(live_statuses),
        }


if __name__ == "__main__":
    reset_schema()
    print("Seeded:", seed())