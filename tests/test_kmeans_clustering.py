"""T28 K-Means behavior tests written before adding persistence/UI."""

import unittest

from app.services.kmeans_clustering_service import (
    KMeansClusteringError,
    cluster_students,
    rank_centroids,
)


def sample_students() -> list[dict[str, object]]:
    points = [
        (101, 96.0, 0, 0), (102, 94.0, 1, 0), (103, 97.0, 0, 1),
        (201, 72.0, 5, 1), (202, 70.0, 6, 2), (203, 68.0, 4, 1),
        (301, 38.0, 13, 5), (302, 42.0, 10, 4), (303, 40.0, 12, 6),
    ]
    return [
        {"student_id": student_id, "attendance_percentage": attendance,
         "late_count": late, "alpha_count": alpha, "eligible": True}
        for student_id, attendance, late, alpha in points
    ]


class KMeansClusteringTests(unittest.TestCase):
    def test_three_quality_bands_receive_directional_labels(self) -> None:
        result = cluster_students(sample_students())

        labels = {item["label"] for item in result["centroids"]}
        self.assertEqual(labels, {"tinggi", "sedang", "rendah"})
        self.assertEqual([item["label"] for item in result["centroids"]],
                         ["tinggi", "sedang", "rendah"])
        high = result["centroids"][0]
        low = result["centroids"][2]
        self.assertGreater(high["attendance_percentage"], low["attendance_percentage"])
        self.assertLess(high["late_count"] + high["alpha_count"],
                        low["late_count"] + low["alpha_count"])
        self.assertEqual(sum(item["student_count"] for item in result["centroids"]), 9)

    def test_same_data_is_reproducible_even_when_row_order_changes(self) -> None:
        rows = sample_students()
        first = cluster_students(rows)
        second = cluster_students(list(reversed(rows)))
        first_assignments = {
            student_id: assignment["cluster_no"]
            for student_id, assignment in first["assignments"].items()
        }
        second_assignments = {
            student_id: assignment["cluster_no"]
            for student_id, assignment in second["assignments"].items()
        }
        self.assertEqual(first_assignments, second_assignments)
        self.assertEqual(first["centroids"], second["centroids"])

    def test_ineligible_rows_are_not_fitted_or_assigned(self) -> None:
        rows = sample_students()
        rows.append({
            "student_id": 999, "attendance_percentage": None,
            "late_count": 5, "alpha_count": 9, "eligible": False,
        })
        result = cluster_students(rows)
        self.assertNotIn(999, result["assignments"])
        self.assertEqual(result["eligible_count"], 9)

    def test_rejects_too_few_eligible_rows_and_less_than_three_patterns(self) -> None:
        with self.assertRaisesRegex(KMeansClusteringError, "minimal tiga siswa"):
            cluster_students(sample_students()[:2])
        identical = [
            {"student_id": 100 + index, "attendance_percentage": 80.0,
             "late_count": 2, "alpha_count": 1, "eligible": True}
            for index in range(3)
        ]
        with self.assertRaisesRegex(KMeansClusteringError, "pola fitur berbeda"):
            cluster_students(identical)

    def test_rejects_nonfinite_out_of_range_and_negative_features(self) -> None:
        for bad in (
            {"attendance_percentage": float("nan"), "late_count": 1, "alpha_count": 0},
            {"attendance_percentage": 101.0, "late_count": 1, "alpha_count": 0},
            {"attendance_percentage": 90.0, "late_count": -1, "alpha_count": 0},
        ):
            rows = sample_students()
            rows[0].update(bad)
            with self.subTest(bad=bad), self.assertRaises(KMeansClusteringError):
                cluster_students(rows)

    def test_centroid_score_tie_uses_feature_direction_then_model_id(self) -> None:
        raw = [
            {"cluster_id": 9, "attendance_percentage": 80.0,
             "late_count": 3.0, "alpha_count": 3.0, "student_count": 2},
            {"cluster_id": 4, "attendance_percentage": 70.0,
             "late_count": 4.0, "alpha_count": 1.0, "student_count": 3},
            {"cluster_id": 7, "attendance_percentage": 60.0,
             "late_count": 3.0, "alpha_count": 4.0, "student_count": 4},
        ]
        standardized = [
            {"attendance_percentage": 1.0, "late_count": 0.0, "alpha_count": 1.0},
            {"attendance_percentage": 0.0, "late_count": 1.0, "alpha_count": -1.0},
            {"attendance_percentage": -1.0, "late_count": 0.0, "alpha_count": 0.0},
        ]

        ranked = rank_centroids(raw, standardized)

        self.assertEqual([item["cluster_id"] for item in ranked], [9, 4, 7])
        self.assertEqual([item["label"] for item in ranked], ["tinggi", "sedang", "rendah"])
        self.assertEqual([item["cluster_no"] for item in ranked], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
