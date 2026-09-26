"""Validated school geofence configuration and server-side location checks."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
from typing import Any

from app.database import get_db, transaction
from app.services.audit_service import record_audit


EARTH_RADIUS_METERS = 6_371_008.8


class GeofenceValidationError(ValueError):
    """Geofence configuration or location input is invalid."""


def _decimal_value(value: Any, label: str, *, places: str) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise GeofenceValidationError(f"{label} tidak valid.")
    if not isinstance(value, (str, int, float, Decimal)):
        raise GeofenceValidationError(f"{label} harus berupa angka.")
    try:
        result = Decimal(str(value).strip()).quantize(Decimal(places))
    except (InvalidOperation, ValueError, TypeError):
        raise GeofenceValidationError(f"{label} harus berupa angka.") from None
    if not result.is_finite():
        raise GeofenceValidationError(f"{label} harus berupa angka terbatas.")
    return result


def validate_geofence_config(*, name: str, latitude: Any, longitude: Any,
                             radius_meters: Any, max_accuracy_meters: Any,
                             is_active: bool) -> dict[str, Any]:
    if not isinstance(name, str) or any(ord(char) < 32 for char in name):
        raise GeofenceValidationError("Nama lokasi tidak valid.")
    normalized_name = " ".join(name.split())
    if not 1 <= len(normalized_name) <= 100:
        raise GeofenceValidationError("Nama lokasi harus berisi 1–100 karakter.")
    lat = _decimal_value(latitude, "Latitude", places="0.0000001")
    lon = _decimal_value(longitude, "Longitude", places="0.0000001")
    if (lat is None) != (lon is None):
        raise GeofenceValidationError("Latitude dan longitude harus diisi bersamaan.")
    if lat is not None and not Decimal("-90") <= lat <= Decimal("90"):
        raise GeofenceValidationError("Latitude harus berada antara -90 dan 90.")
    if lon is not None and not Decimal("-180") <= lon <= Decimal("180"):
        raise GeofenceValidationError("Longitude harus berada antara -180 dan 180.")
    if isinstance(radius_meters, bool):
        raise GeofenceValidationError("Radius harus berupa bilangan meter positif.")
    try:
        radius = int(str(radius_meters).strip())
    except (ValueError, TypeError):
        raise GeofenceValidationError("Radius harus berupa bilangan meter positif.") from None
    if radius <= 0:
        raise GeofenceValidationError("Radius harus lebih besar dari nol.")
    accuracy = _decimal_value(max_accuracy_meters, "Batas accuracy", places="0.01")
    if accuracy is not None and accuracy <= 0:
        raise GeofenceValidationError("Batas accuracy harus lebih besar dari nol.")
    if type(is_active) is not bool:
        raise GeofenceValidationError("Status geofence tidak valid.")
    if is_active and (lat is None or accuracy is None):
        raise GeofenceValidationError(
            "Isi koordinat sekolah dan batas accuracy yang disepakati sebelum mengaktifkan geofence."
        )
    return {"name": normalized_name, "latitude": lat, "longitude": lon,
            "radius_meters": radius, "max_accuracy_meters": accuracy,
            "is_active": is_active}


def get_geofence_config() -> dict[str, Any]:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id, name, latitude, longitude, radius_meters,
                      max_accuracy_meters, is_active, updated_by_user_id, updated_at
               FROM school_geofences WHERE id=1 LIMIT 1"""
        )
        current = cursor.fetchone()
    if current is not None:
        return current
    return {"id": 1, "name": "Sekolah", "latitude": None, "longitude": None,
            "radius_meters": 75, "max_accuracy_meters": None, "is_active": False,
            "updated_by_user_id": None, "updated_at": None}


def save_geofence_config(*, actor_user_id: int, name: str, latitude: Any,
                         longitude: Any, radius_meters: Any,
                         max_accuracy_meters: Any, is_active: bool) -> dict[str, Any]:
    if type(actor_user_id) is not int or actor_user_id <= 0:
        raise GeofenceValidationError("Pelaku perubahan tidak valid.")
    values = validate_geofence_config(
        name=name, latitude=latitude, longitude=longitude, radius_meters=radius_meters,
        max_accuracy_meters=max_accuracy_meters, is_active=is_active,
    )
    with transaction() as (_, cursor):
        cursor.execute("SELECT name, latitude, longitude, radius_meters, max_accuracy_meters, is_active "
                       "FROM school_geofences WHERE id=1 FOR UPDATE")
        previous = cursor.fetchone()
        cursor.execute(
            """INSERT INTO school_geofences
               (id, name, latitude, longitude, radius_meters, max_accuracy_meters,
                is_active, updated_by_user_id)
               VALUES (1, %s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE name=VALUES(name), latitude=VALUES(latitude),
                 longitude=VALUES(longitude), radius_meters=VALUES(radius_meters),
                 max_accuracy_meters=VALUES(max_accuracy_meters), is_active=VALUES(is_active),
                 updated_by_user_id=VALUES(updated_by_user_id)""",
            (values["name"], values["latitude"], values["longitude"], values["radius_meters"],
             values["max_accuracy_meters"], values["is_active"], actor_user_id),
        )
        changed = previous is None or any(
            previous[key] != values[key] for key in
            ("name", "latitude", "longitude", "radius_meters", "max_accuracy_meters", "is_active")
        )
        if changed:
            fields = [key for key in
                      ("name", "latitude", "longitude", "radius_meters", "max_accuracy_meters", "is_active")
                      if previous is None or previous[key] != values[key]]
            record_audit(cursor, actor_user_id=actor_user_id, action="geofence_updated",
                         target_type="geofence", target_id=1,
                         metadata={"is_active": is_active, "fields": fields})
    return get_geofence_config()


def haversine_meters(latitude_a: Any, longitude_a: Any,
                     latitude_b: Any, longitude_b: Any) -> float:
    points = []
    for value, label in ((latitude_a, "Latitude"), (longitude_a, "Longitude"),
                         (latitude_b, "Latitude"), (longitude_b, "Longitude")):
        parsed = _decimal_value(value, label, places="0.0000001")
        if parsed is None:
            raise GeofenceValidationError(f"{label} wajib diisi.")
        points.append(float(parsed))
    lat_a, lon_a, lat_b, lon_b = points
    if not (-90 <= lat_a <= 90 and -90 <= lat_b <= 90
            and -180 <= lon_a <= 180 and -180 <= lon_b <= 180):
        raise GeofenceValidationError("Koordinat harus berada dalam rentang bumi.")
    lat1, lat2 = math.radians(lat_a), math.radians(lat_b)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(lon_b - lon_a)
    haversine = (math.sin(delta_lat / 2) ** 2
                 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2)
    angle = 2 * math.atan2(math.sqrt(haversine), math.sqrt(max(0.0, 1.0 - haversine)))
    return EARTH_RADIUS_METERS * angle


def evaluate_location(*, latitude: Any, longitude: Any, accuracy_meters: Any,
                      config: dict[str, Any] | None = None) -> dict[str, Any]:
    fence = get_geofence_config() if config is None else config
    if (not fence.get("is_active") or fence.get("latitude") is None
            or fence.get("longitude") is None or fence.get("max_accuracy_meters") is None):
        return {"allowed": False, "reason": "not_configured", "distance_meters": None}
    try:
        accuracy = _decimal_value(accuracy_meters, "Accuracy lokasi", places="0.01")
        if accuracy is None or accuracy < 0:
            raise GeofenceValidationError("Accuracy lokasi harus berupa angka nol atau lebih.")
        point_lat = _decimal_value(latitude, "Latitude", places="0.0000001")
        point_lon = _decimal_value(longitude, "Longitude", places="0.0000001")
        if point_lat is None or point_lon is None:
            raise GeofenceValidationError("Koordinat lokasi wajib diisi.")
        if not Decimal("-90") <= point_lat <= Decimal("90"):
            raise GeofenceValidationError("Latitude lokasi di luar rentang.")
        if not Decimal("-180") <= point_lon <= Decimal("180"):
            raise GeofenceValidationError("Longitude lokasi di luar rentang.")
    except GeofenceValidationError as error:
        return {"allowed": False, "reason": "invalid_location", "message": str(error),
                "distance_meters": None}
    if accuracy > Decimal(str(fence["max_accuracy_meters"])):
        return {"allowed": False, "reason": "accuracy_unreliable", "distance_meters": None}
    distance = haversine_meters(point_lat, point_lon, fence["latitude"], fence["longitude"])
    inside = distance <= int(fence["radius_meters"])
    return {"allowed": inside, "reason": "inside" if inside else "outside",
            "distance_meters": round(distance, 1)}
