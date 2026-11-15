"""Capacity matching: which bus departure should a parcel go on?

Phase 1 is a transparent scoring rule (explainable to the jury). Phase 2 adds a small,
capped nudge from the forecasting model. Feasibility (free space, timing) stays rule-based,
so the model can never overbook a bus.
"""
from datetime import timedelta

import forecast

MIN_BUFFER_MINUTES = 20      # parcel must be dropped at least this long before departure
WAIT_PENALTY_PER_HOUR = 1.0  # waiting longer is worse
FILL_BONUS = 3.0             # prefer buses that are already partly full (consolidation = fewer wasted trips)
TIGHT_PENALTY = 2.0          # avoid buses that would end up >90% full (risk of overflow)
BASE_SCORE = 10.0

FORECAST_WEIGHT = 2.0        # AI: bonus for buses forecast under half full, penalty for forecast-full ones
FORECAST_CAP = 1.0           # ... but never more than +/-1 point
DELAY_FREE_MIN = 10          # AI: delays up to this many minutes are not penalised
DELAY_PENALTY_PER_MIN = 0.1


def _forecast(d):
    fill = forecast.predict_fill(d.route_id, d.departs_at)
    delay = forecast.predict_delay(d.route_id, d.departs_at)
    return (fill, delay) if fill is not None and delay is not None else None


def rank_departures(departures, weight_kg, ready_at):
    """Return feasible departures sorted best-first.

    Each item: {"departure": <Departure>, "score": float, "reasons": [str, ...]}
    """
    earliest = ready_at + timedelta(minutes=MIN_BUFFER_MINUTES)
    ranked = []

    for d in departures:
        free = d.capacity_kg - d.booked_kg
        if d.departs_at < earliest or free < weight_kg:
            continue  # too soon, or not enough free space

        wait_h = (d.departs_at - ready_at).total_seconds() / 3600
        fill_before = d.booked_kg / d.capacity_kg
        fill_after = (d.booked_kg + weight_kg) / d.capacity_kg

        score = BASE_SCORE - WAIT_PENALTY_PER_HOUR * wait_h + FILL_BONUS * fill_before
        reasons = [
            f"departs in {wait_h:.1f} h",
            f"{free:.0f} kg free, parcel needs {weight_kg:g} kg",
        ]
        if fill_before > 0:
            reasons.append(f"bus already {fill_before:.0%} full - consolidates shipments")
        if fill_after > 0.9:
            score -= TIGHT_PENALTY
            reasons.append("bus would be almost full (small penalty)")

        guess = _forecast(d)
        if guess:
            exp_fill, exp_delay = guess
            score += max(-FORECAST_CAP, min(FORECAST_CAP, FORECAST_WEIGHT * (0.5 - exp_fill)))
            reasons.append(f"AI forecast: usually {exp_fill:.0%} full at this time")
            if exp_delay > DELAY_FREE_MIN:
                score -= DELAY_PENALTY_PER_MIN * (exp_delay - DELAY_FREE_MIN)
                reasons.append(f"AI forecast: usually about {exp_delay:.0f} min late")

        ranked.append({"departure": d, "score": score, "reasons": reasons})

    ranked.sort(key=lambda r: (-r["score"], r["departure"].departs_at))
    return ranked