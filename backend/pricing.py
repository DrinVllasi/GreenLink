"""Placeholder pricing. We'll make this smarter (capacity-aware) in a later step."""

BASE_FEE = 1.00
PER_KM = 0.03
PER_KG = 0.20


def price_for(distance_km: float, weight_kg: float) -> float:
    return round(BASE_FEE + PER_KM * distance_km + PER_KG * weight_kg, 2)
