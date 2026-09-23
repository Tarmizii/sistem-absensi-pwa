"""Exercise geofence persistence, server decisions, audit, and cleanup in dev MySQL."""

from __future__ import annotations

import secrets
from unittest.mock import patch

from pymysql import MySQLError

from app import create_app
from app.database import get_db, transaction
from app.services.geofence_service import evaluate_location, save_geofence_config


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke test hanya untuk database development/test.")
    suffix = secrets.token_hex(4)
    smoke_name = f"Uji T13 {suffix}"
    context = app.app_context()
    context.push()
    actor_id = None
    baseline_audit_ids: set[int] = set()
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE role='admin' AND is_active=1 ORDER BY id LIMIT 1")
            actor = cursor.fetchone()
            cursor.execute("SELECT id FROM school_geofences WHERE id=1")
            configured = cursor.fetchone()
            cursor.execute("SELECT id FROM audit_logs WHERE target_type='geofence' AND target_id=1")
            baseline_audit_ids = {int(row["id"]) for row in cursor.fetchall()}
        if actor is None:
            raise SystemExit("Akun Admin aktif belum tersedia.")
        if configured is not None:
            raise SystemExit("Geofence sudah dikonfigurasi; smoke menolak mengubah data sekolah.")
        actor_id = int(actor["id"])

        try:
            with patch("app.services.geofence_service.record_audit",
                       side_effect=MySQLError("synthetic audit failure")):
                save_geofence_config(actor_user_id=actor_id, name=smoke_name, latitude=0,
                                     longitude=0, radius_meters=75,
                                     max_accuracy_meters=30, is_active=True)
        except MySQLError:
            pass
        else:
            raise AssertionError("kegagalan audit tidak membatalkan perubahan geofence")
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM school_geofences WHERE id=1")
            assert cursor.fetchone() is None

        save_geofence_config(actor_user_id=actor_id, name=smoke_name, latitude=0, longitude=0,
                             radius_meters=75, max_accuracy_meters=30, is_active=True)
        center = evaluate_location(latitude=0, longitude=0, accuracy_meters=5)
        outside = evaluate_location(latitude=0, longitude=0.001, accuracy_meters=5)
        unreliable = evaluate_location(latitude=0, longitude=0, accuracy_meters=31)
        invalid = evaluate_location(latitude=91, longitude=0, accuracy_meters=5)
        assert center["reason"] == "inside" and center["allowed"]
        assert outside["reason"] == "outside" and not outside["allowed"]
        assert unreliable["reason"] == "accuracy_unreliable" and not unreliable["allowed"]
        assert invalid["reason"] == "invalid_location" and not invalid["allowed"]

        save_geofence_config(actor_user_id=actor_id, name=smoke_name, latitude=0, longitude=0,
                             radius_meters=76, max_accuracy_meters=30, is_active=True)
        with get_db().cursor() as cursor:
            cursor.execute("SELECT action FROM audit_logs WHERE target_type='geofence' AND target_id=1")
            actions = {row["action"] for row in cursor.fetchall()}
        assert "geofence_updated" in actions
        print("t13_mysql_smoke=ok; audit_rollback=ok; inside=ok; outside=ok; accuracy=ok; invalid=ok; cleanup=ok")
    finally:
        try:
            with transaction() as (_, cursor):
                cursor.execute("SELECT id, name, updated_by_user_id FROM school_geofences WHERE id=1 FOR UPDATE")
                current = cursor.fetchone()
                if current and current["name"] == smoke_name and int(current["updated_by_user_id"] or 0) == actor_id:
                    cursor.execute("DELETE FROM school_geofences WHERE id=1")
                cursor.execute("SELECT id FROM audit_logs WHERE target_type='geofence' AND target_id=1")
                created_ids = [int(row["id"]) for row in cursor.fetchall()
                               if int(row["id"]) not in baseline_audit_ids]
                if created_ids:
                    cursor.execute("DELETE FROM audit_logs WHERE id IN (%s)" %
                                   ",".join(["%s"] * len(created_ids)), tuple(created_ids))
        finally:
            context.pop()


if __name__ == "__main__":
    main()
