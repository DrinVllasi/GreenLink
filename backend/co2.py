"""CO2 + credits logic. Numbers follow the concept document (section 8.2).

All constants are ASSUMPTIONS to be validated in the pilot - keep them in one place
so you can show them on screen and change them easily.
"""
import math

VAN_KG_CO2_PER_KM = 0.225            # light diesel van, midpoint of 0.2-0.25 kg CO2e/km
REFERENCE_PARCELS_PER_VAN_TRIP = 10  # a dedicated van trip is shared by ~10 parcels
BUS_MARGINAL_KG_CO2_PER_KG_KM = 0.0003  # extra fuel burned by a bus carrying 1 more kg over 1 km (assumption)
CREDITS_PER_KG_CO2 = 10              # 1 kg CO2 avoided -> 10 credits
CREDIT_VALUE_EUR = 0.008             # 1 credit = 0.008 EUR, so 1 kg CO2 = 10 credits = 0.08 EUR (~80 EUR/t, close to the EU ETS price)
REDEEM_CAP_SHARE = 0.25              # credits may pay at most 25% of a parcel's price


def co2_avoided(distance_km: float, weight_kg: float) -> float:
    """kg CO2e avoided for one parcel vs. a dedicated round-trip van, minus the bus's marginal emissions."""
    van_share = VAN_KG_CO2_PER_KM * (distance_km * 2) / REFERENCE_PARCELS_PER_VAN_TRIP
    bus_marginal = BUS_MARGINAL_KG_CO2_PER_KG_KM * weight_kg * distance_km
    return round(max(van_share - bus_marginal, 0.0), 2)


def credits_for(co2_kg: float) -> int:
    return int(round(co2_kg * CREDITS_PER_KG_CO2))


def credits_to_eur(credits: int) -> float:
    return round(credits * CREDIT_VALUE_EUR, 2)

def max_redeemable(price: float, balance: int) -> tuple[int, float]:
    """How many credits can be used on a parcel of this price, and the EUR discount they give."""
    max_discount = price * REDEEM_CAP_SHARE
    credits = min(max(int(balance), 0), math.floor(max_discount / CREDIT_VALUE_EUR + 1e-9))
    return credits, round(credits * CREDIT_VALUE_EUR, 2)