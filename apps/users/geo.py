from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_KM * c


def get_lat_lng(obj, lat_attr="latitude", lng_attr="longitude"):
    lat = getattr(obj, lat_attr, None)
    lng = getattr(obj, lng_attr, None)
    if lat is None or lng is None:
        return None, None
    return float(lat), float(lng)


def to_wkt_point(lat, lng):
    if lat is None or lng is None:
        return None
    # WKT format, lng first then lat.
    return f"POINT({float(lng)} {float(lat)})"
