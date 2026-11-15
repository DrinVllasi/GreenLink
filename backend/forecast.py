"""Capacity-matching AI, phase 2: forecasts bus fill and delay from past departures.

A small random forest per target, trained on SIMULATED demo data (see seed.py). It shows the
phase-2 pipeline (history -> model -> forecast); real accuracy needs real scan history.
If training fails or data is too thin, predict_* return None and the app uses the base price.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy import select

import models as m
from database import SessionLocal

HOLDOUT_DAYS = 14   # the newest days are kept aside to test the model on data it has not seen
MIN_ROWS = 200      # below this the forecast is switched off
FILL_MIN, FILL_MAX = 0.05, 0.98
MODEL_LABEL = "Random forest trained on simulated demo data"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_state = {"fill": None, "delay": None, "metrics": None, "table": []}


def _features(route_id, departs_at):
    t = departs_at.astimezone(timezone.utc)
    return [route_id, t.weekday(), t.hour]


def _forest(leaf=3):
    return RandomForestRegressor(n_estimators=100, max_depth=8, min_samples_leaf=leaf, random_state=42)


def _mae(actual, predicted):
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(predicted))))


def is_ready():
    return _state["fill"] is not None and _state["delay"] is not None


def train(db=None):
    """Train from the database. Returns the metrics dict, or None if forecasting is unavailable."""
    try:
        if db is None:
            with SessionLocal() as own:
                return _train(own)
        return _train(db)
    except Exception as exc:  # never let a model problem break the app
        print("Forecast training failed:", exc)
        _state.update(fill=None, delay=None, metrics=None, table=[])
        return None


def _train(db):
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(m.Departure)
        .where(m.Departure.departs_at < now, m.Departure.delay_min.is_not(None))
        .order_by(m.Departure.departs_at)
    ).all()
    if len(rows) < MIN_ROWS:
        raise ValueError(f"only {len(rows)} past departures, need {MIN_ROWS}")

    X = np.array([_features(d.route_id, d.departs_at) for d in rows], dtype=float)
    y_fill = np.array([d.booked_kg / d.capacity_kg for d in rows])
    y_delay = np.array([d.delay_min for d in rows], dtype=float)

    cutoff = now - timedelta(days=HOLDOUT_DAYS)
    is_test = np.array([d.departs_at < now and d.departs_at >= cutoff for d in rows])
    train_mask = ~is_test
    if is_test.sum() < 20 or train_mask.sum() < 100:
        raise ValueError("not enough data for a hold-out split")

    # 1) honest evaluation: fit on older days, score on the newest days
    fill_eval, delay_eval = _forest(), _forest(10)
    fill_eval.fit(X[train_mask], y_fill[train_mask])
    delay_eval.fit(X[train_mask], y_delay[train_mask])
    fill_pred = fill_eval.predict(X[is_test])
    delay_pred = delay_eval.predict(X[is_test])
    metrics = {
        "label": MODEL_LABEL,
        "data": "simulated demo data",
        "train_rows": int(train_mask.sum()),
        "test_rows": int(is_test.sum()),
        "holdout_days": HOLDOUT_DAYS,
        "fill_mae_pp": round(_mae(y_fill[is_test], fill_pred) * 100, 1),
        "fill_baseline_mae_pp": round(_mae(y_fill[is_test], np.full(is_test.sum(), y_fill[train_mask].mean())) * 100, 1),
        "delay_mae_min": round(_mae(y_delay[is_test], delay_pred), 1),
        "delay_baseline_mae_min": round(_mae(y_delay[is_test], np.full(is_test.sum(), y_delay[train_mask].mean())), 1),
        "trained_at": now.isoformat(),
    }

    # 2) the model that is actually used: refit on all the data
    fill_model, delay_model = _forest(), _forest(10)
    fill_model.fit(X, y_fill)
    delay_model.fit(X, y_delay)

    # 3) forecast table for the admin screen: every route x weekday x departure hour
    hours = sorted({d.departs_at.astimezone(timezone.utc).hour for d in rows})
    grid, labels = [], []
    for route in db.scalars(select(m.Route).order_by(m.Route.id)).all():
        for weekday in range(7):
            for hour in hours:
                grid.append([route.id, weekday, hour])
                labels.append((route.id, f"{route.origin.city} to {route.destination.city}", weekday, hour))
    fills = np.clip(fill_model.predict(np.array(grid, dtype=float)), FILL_MIN, FILL_MAX)
    delays = delay_model.predict(np.array(grid, dtype=float))
    table = [
        {"route_id": rid, "route": name, "weekday": WEEKDAYS[wd], "hour_utc": hr,
         "expected_fill_pct": round(float(f) * 100), "expected_delay_min": round(float(dl), 1)}
        for (rid, name, wd, hr), f, dl in zip(labels, fills, delays)
    ]

    lookup = {(g[0], g[1], g[2]): (float(f), float(dl)) for g, f, dl in zip(grid, fills, delays)}
    _state.update(fill=fill_model, delay=delay_model, metrics=metrics, table=table, lookup=lookup)
    return metrics


def predict_fill(route_id, departs_at):
    """Expected fill (0.05 to 0.98) of a departure, or None if the model is not available."""
    if _state["fill"] is None:
        return None
    hit = _state.get("lookup", {}).get(tuple(_features(route_id, departs_at)))
    return hit[0] if hit else None


def predict_delay(route_id, departs_at):
    """Expected delay in minutes, or None if the model is not available."""
    if _state["fill"] is None:
        return None
    hit = _state.get("lookup", {}).get(tuple(_features(route_id, departs_at)))
    return max(0.0, hit[1]) if hit else None


_last_try = [0.0]


def ensure_ready():
    """If the model is not trained (e.g. before a reseed), retry at most once a minute."""
    import time
    if is_ready() or time.time() - _last_try[0] < 60:
        return
    _last_try[0] = time.time()
    train()

def get_metrics():
    return _state["metrics"]


def get_table():
    return _state["table"]


if __name__ == "__main__":
    metrics = train()
    if not metrics:
        print("Forecast not available.")
    else:
        for key, value in metrics.items():
            print(f"{key}: {value}")
        # next Friday and next Sunday, Prishtine to Prizren (route 1)
        today = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        for label, weekday, hour in [("Fri 07:00", 4, 7), ("Sun 10:00", 6, 10)]:
            day = today + timedelta(days=(weekday - today.weekday()) % 7 or 7)
            when = day.replace(hour=hour)
            print(f"{label} route 1: fill {predict_fill(1, when):.0%}, delay {predict_delay(1, when):.1f} min")