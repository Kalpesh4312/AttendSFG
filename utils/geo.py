"""
Geo-fencing helpers.

We use the Haversine formula to compute the great-circle distance between
the classroom location (captured by the teacher's device when a session is
started) and the student's location (captured at the moment they mark
attendance). If the distance exceeds the session's configured radius, the
attendance attempt is rejected.
"""
import math


EARTH_RADIUS_METERS = 6371000


def haversine_distance_meters(lat1, lon1, lat2, lon2):
    """Return the distance in meters between two lat/lon points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_METERS * c


def is_within_geofence(class_lat, class_lon, student_lat, student_lon, radius_meters):
    distance = haversine_distance_meters(class_lat, class_lon, student_lat, student_lon)
    return distance <= radius_meters, distance
