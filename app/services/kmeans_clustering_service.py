"""Reproducible three-feature K-Means pipeline (T28)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


CLUSTER_COUNT = 3
RANDOM_STATE = 42
N_INIT = 10
FORMULA_VERSION = "prd-attendance-v1"
LABEL_RULE_VERSION = "z_attendance-z_late-z_alpha; ties attendance-desc-late-asc-alpha-asc-id-asc-v1"
FEATURE_FIELDS = ("attendance_percentage", "late_count", "alpha_count")
CLUSTER_LABELS = ("tinggi", "sedang", "rendah")


class KMeansClusteringError(ValueError):
    """The feature rows cannot produce three distinct clusters."""


def _numeric_features(row: dict[str, Any]) -> tuple[float, float, float]:
    try:
        attendance = float(row["attendance_percentage"])
        late = float(row["late_count"])
        alpha = float(row["alpha_count"])
    except (KeyError, TypeError, ValueError, OverflowError):
        raise KMeansClusteringError("Nilai fitur siswa tidak lengkap atau tidak valid.") from None
    if (not all(math.isfinite(value) for value in (attendance, late, alpha))
            or attendance < 0 or attendance > 100 or late < 0 or alpha < 0
            or not late.is_integer() or not alpha.is_integer()):
        raise KMeansClusteringError("Nilai fitur siswa tidak valid untuk K-Means.")
    return attendance, late, alpha


def rank_centroids(raw_centroids: list[dict[str, Any]],
                   standardized_centroids: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank clusters by attendance up and lateness/Alpa down, with fixed ties."""

    if len(raw_centroids) != CLUSTER_COUNT or len(standardized_centroids) != CLUSTER_COUNT:
        raise KMeansClusteringError("K-Means tidak menghasilkan tepat tiga centroid.")
    pairs: list[tuple[tuple[float, float, float, float, int], dict[str, Any]]] = []
    for raw, standardized in zip(raw_centroids, standardized_centroids):
        try:
            cluster_id = int(raw["cluster_id"])
            score = (float(standardized["attendance_percentage"])
                     - float(standardized["late_count"])
                     - float(standardized["alpha_count"]))
            attendance = float(raw["attendance_percentage"])
            late = float(raw["late_count"])
            alpha = float(raw["alpha_count"])
        except (KeyError, TypeError, ValueError, OverflowError):
            raise KMeansClusteringError("Centroid K-Means tidak valid.") from None
        if not all(math.isfinite(value) for value in (score, attendance, late, alpha)):
            raise KMeansClusteringError("Centroid K-Means tidak valid.")
        key = (-score, -attendance, late, alpha, cluster_id)
        pairs.append((key, raw))
    pairs.sort(key=lambda item: item[0])
    ranked: list[dict[str, Any]] = []
    for cluster_no, (_, raw) in enumerate(pairs, start=1):
        ranked.append({**raw, "cluster_no": cluster_no, "label": CLUSTER_LABELS[cluster_no - 1]})
    return ranked


def cluster_students(students: list[dict[str, Any]]) -> dict[str, Any]:
    """Fit K=3 on eligible students and return stable semantic labels and centroids."""

    if not isinstance(students, list):
        raise KMeansClusteringError("Data siswa untuk K-Means tidak valid.")
    eligible: list[tuple[int, dict[str, Any], tuple[float, float, float]]] = []
    seen_ids: set[int] = set()
    for row in students:
        if not isinstance(row, dict):
            raise KMeansClusteringError("Data siswa untuk K-Means tidak valid.")
        if row.get("eligible") is False:
            continue
        student_id = row.get("student_id")
        if not isinstance(student_id, int) or isinstance(student_id, bool) or student_id <= 0:
            raise KMeansClusteringError("Identitas fitur siswa tidak valid.")
        if student_id in seen_ids:
            raise KMeansClusteringError("Siswa duplikat pada dataset K-Means.")
        seen_ids.add(student_id)
        eligible.append((student_id, row, _numeric_features(row)))

    if len(eligible) < CLUSTER_COUNT:
        raise KMeansClusteringError("Analisis memerlukan minimal tiga siswa yang layak.")
    eligible.sort(key=lambda item: item[0])
    patterns = {features for _, _, features in eligible}
    if len(patterns) < CLUSTER_COUNT:
        raise KMeansClusteringError("Analisis memerlukan minimal tiga pola fitur berbeda.")

    values = np.asarray([features for _, _, features in eligible], dtype=np.float64)
    scaler = StandardScaler()
    scaled_values = scaler.fit_transform(values)
    model = KMeans(n_clusters=CLUSTER_COUNT, random_state=RANDOM_STATE,
                   n_init=N_INIT, algorithm="lloyd")
    try:
        model.fit(scaled_values)
    except (ValueError, FloatingPointError) as error:
        raise KMeansClusteringError("Model K-Means tidak dapat dibentuk dari fitur ini.") from error

    model_labels = np.asarray(model.labels_, dtype=np.int64)
    cluster_ids, cluster_sizes = np.unique(model_labels, return_counts=True)
    if len(cluster_ids) != CLUSTER_COUNT or np.any(cluster_sizes == 0):
        raise KMeansClusteringError("Data tidak membentuk tiga cluster yang terisi.")

    raw_centers = scaler.inverse_transform(model.cluster_centers_)
    raw_centroids: list[dict[str, Any]] = []
    standardized_centroids: list[dict[str, Any]] = []
    sizes_by_cluster = {int(cluster_id): int(size)
                        for cluster_id, size in zip(cluster_ids, cluster_sizes)}
    for cluster_id, raw_values, scaled in zip(range(CLUSTER_COUNT), raw_centers,
                                               model.cluster_centers_):
        raw_centroids.append({
            "cluster_id": cluster_id,
            "attendance_percentage": round(float(raw_values[0]), 4),
            "late_count": round(float(raw_values[1]), 4),
            "alpha_count": round(float(raw_values[2]), 4),
            "student_count": sizes_by_cluster.get(cluster_id, 0),
        })
        standardized_centroids.append({
            "attendance_percentage": float(scaled[0]),
            "late_count": float(scaled[1]),
            "alpha_count": float(scaled[2]),
        })

    ranked_centroids = rank_centroids(raw_centroids, standardized_centroids)
    ranked_by_model_id = {int(item["cluster_id"]): item for item in ranked_centroids}
    assignments: dict[int, dict[str, Any]] = {}
    for (student_id, _, _), model_label in zip(eligible, model_labels):
        centroid = ranked_by_model_id[int(model_label)]
        assignments[student_id] = {
            "cluster_no": int(centroid["cluster_no"]),
            "label": str(centroid["label"]),
        }

    stored_centroids = [{
        "cluster_no": int(item["cluster_no"]),
        "label": str(item["label"]),
        "attendance_percentage": item["attendance_percentage"],
        "late_count": item["late_count"],
        "alpha_count": item["alpha_count"],
        "student_count": item["student_count"],
    } for item in ranked_centroids]
    return {
        "eligible_count": len(eligible),
        "assignments": assignments,
        "centroids": stored_centroids,
        "formula_version": FORMULA_VERSION,
        "label_rule_version": LABEL_RULE_VERSION,
        "random_state": RANDOM_STATE,
        "n_init": N_INIT,
    }
