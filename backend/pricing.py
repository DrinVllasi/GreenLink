"""Pricing: a base formula plus a bounded AI demand adjustment."""

BASE_FEE = 1.00
PER_KM = 0.03
PER_KG = 0.20

PRICE_CAP = 0.15      # the AI can never move the price by more than +/-15%
NEUTRAL_FILL = 0.55   # forecast fill at which no adjustment applies
SENSITIVITY = 0.5     # +10 points of expected fill = +5% price


def price_for(distance_km: float, weight_kg: float) -> float:
    return round(BASE_FEE + PER_KM * distance_km + PER_KG * weight_kg, 2)


def dynamic_price(base_price: float, expected_fill):
    """Return (price, adjustment_pct). Usually-empty bus = discount, usually-full bus = surcharge."""
    if expected_fill is None:
        return base_price, 0
    adjustment = max(-PRICE_CAP, min(PRICE_CAP, (expected_fill - NEUTRAL_FILL) * SENSITIVITY))
    pct = round(adjustment * 100)
    return round(base_price * (1 + pct / 100), 2), pct