from decimal import Decimal


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
