"""Shared geo math - just the one formula, used everywhere something needs
a real distance between two lat/lng points (farm search in routers/farms.py,
the delivery-route ordering in routers/admin.py). One place for it so the
rounding behavior can't quietly drift between callers.
"""
import math


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    # whole km, matching frontend/index.html's distanceKm() rounding - keeps
    # a farm right at a radius boundary consistent between the offline demo
    # and this real endpoint instead of one keeping a decimal the other drops
    return round(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))
