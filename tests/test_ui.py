"""Route/template checks for the T05 role shells and shared styles."""

from __future__ import annotations

from contextlib import nullcontext
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from app import create_app
from app.services.auth_service import credential_stamp


USERS = {
    "admin": {
        "id": 1,
        "username": "admin.test",
        "password_hash": "unused",
        "role": "admin",
        "is_active": 1,
        "must_change_password": 0,
    },
    "teacher": {
        "id": 2,
        "username": "teacher.test",
        "password_hash": "unused",
        "role": "teacher",
        "is_active": 1,
        "must_change_password": 0,
    },
    "student": {
        "id": 3,
        "username": "student.test",
        "password_hash": "unused",
        "role": "student",
        "is_active": 1,
        "must_change_password": 0,
        "face_registered": 1,
    },
}


def _relative_luminance(color: str) -> float:
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
              for channel in channels]
    return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def _contrast_ratio(first: str, second: str) -> float:
    luminances = sorted((_relative_luminance(first), _relative_luminance(second)))
    return (luminances[1] + 0.05) / (luminances[0] + 0.05)


class RoleShellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-secret"})
        self.client = self.app.test_client()

    def get_as(self, role: str, path: str):
        user = USERS[role]
        state_patch = nullcontext()
        if role == "student" and path == "/student/dashboard":
            # The student home now derives state from the database (T17); the
            # shell test only checks navigation markup, so supply a fixed state.
            state_patch = patch(
                "app.services.attendance_state_service.get_student_day_state",
                return_value={
                    "student_id": 3, "full_name": "student.test",
                    "face_registered": True, "class_name": None,
                    "today": "2026-09-24", "server_time": "07:00",
                    "state": "checkin", "cta_label": "Presensi Masuk",
                    "cta_enabled": True, "reason": None,
                    "status_today": "Belum Absen", "status_source": None,
                    "schedule": {"for_date": "2026-09-24", "checkin_start": "06:30",
                                 "late_after": "07:15", "checkin_cutoff": "08:00",
                                 "checkout_start": "15:00", "is_holiday": False,
                                 "source": "regular"},
                    "can_checkin": True, "can_checkout_now": False,
                },
            )
        with patch("app.services.auth_service.fetch_active_user", return_value=user):
            with state_patch:
                with self.app.app_context(), self.client.session_transaction() as session:
                    session["user_id"] = user["id"]
                    session["credential_stamp"] = credential_stamp(user["password_hash"])
                return self.client.get(path)

    def test_home_and_login_use_shared_stylesheet(self) -> None:
        home = self.client.get("/")
        login = self.client.get("/login")
        self.assertEqual(home.status_code, 200)
        self.assertEqual(login.status_code, 200)
        self.assertIn("css/app.css", home.get_data(as_text=True))
        self.assertIn("Masuk ke ruang kerja Anda", login.get_data(as_text=True))
        self.assertIn("illustrations/school-day-v2.webp", login.get_data(as_text=True))
        self.assertIn("js/password-visibility.js", login.get_data(as_text=True))
        self.assertIn('class="auth-page login-page"', login.get_data(as_text=True))
        self.assertIn("Masuk ke Presensi", login.get_data(as_text=True))
        self.assertNotIn("login-page", home.get_data(as_text=True))
        for field in ("username", "password", "csrf_token"):
            self.assertEqual(login.get_data(as_text=True).count(f'name="{field}"'), 1)

    def test_three_role_shells_render_with_role_navigation(self) -> None:
        cases = (
            ("admin", "/admin/dashboard", "Navigasi Admin", "Monitoring Presensi"),
            ("teacher", "/teacher/dashboard", "Navigasi Guru", "Presensi Kelas"),
            ("student", "/student/dashboard", "Navigasi Siswa", "Riwayat"),
        )
        for role, path, navigation, expected_text in cases:
            with self.subTest(role=role):
                response = self.get_as(role, path)
                body = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(navigation, body)
                self.assertIn(expected_text, body)
                if role == "student":
                    self.assertIn('href="/student/history"', body)
                    self.assertNotIn('aria-disabled="true"', body)
                elif role == "teacher":
                    self.assertIn('href="/teacher/attendance"', body)
                    self.assertIn('href="/teacher/students"', body)
                    self.assertNotIn('aria-disabled="true"', body)
                else:
                    self.assertIn('href="/admin/analytics"', body)
                    self.assertNotIn('title="Analitik belum tersedia"', body)

    def test_compiled_css_is_served_with_new_palette_tokens(self) -> None:
        response = self.client.get("/static/css/app.css")
        self.assertEqual(response.status_code, 200)
        css = response.get_data(as_text=True)
        response.close()
        self.assertIn("#a6412d", css.lower())
        self.assertIn("#fff5e3", css.lower())
        self.assertIn("#ed896f", css.lower())
        self.assertIn("#7cd3aa", css.lower())
        self.assertIn("1.5rem", css)
        self.assertIn("var(--radius-card)", css)
        self.assertIn("var(--shadow-card)", css)

    def test_shared_text_and_status_colors_meet_contrast_targets(self) -> None:
        css = Path("app/static/css/tailwind.input.css").read_text(encoding="utf-8").lower()
        theme = css.split("@font-face", maxsplit=1)[0]
        tokens = dict(re.findall(r"--color-([\w-]+):\s*(#[0-9a-f]{6})", theme))
        self.assertGreaterEqual(_contrast_ratio("#ffffff", tokens["primary"]), 4.5)
        self.assertGreaterEqual(_contrast_ratio(tokens["muted"], tokens["cream"]), 4.5)
        self.assertGreaterEqual(_contrast_ratio(tokens["muted"], tokens["surface"]), 4.5)
        for surface in ("coral", "mint", "warm-yellow", "lime"):
            with self.subTest(surface=surface):
                self.assertGreaterEqual(
                    _contrast_ratio(tokens["ink"], tokens[surface]), 4.5
                )
        self.assertGreaterEqual(_contrast_ratio(tokens["control-border"], tokens["surface"]), 3)
        self.assertGreaterEqual(_contrast_ratio(tokens["control-border"], tokens["cream"]), 3)
        for class_name, foreground in (
            ("status-info", tokens["primary"]),
            ("status-success", tokens["success"]),
            ("status-warning", tokens["warning"]),
            ("status-danger", tokens["danger"]),
        ):
            rule = re.search(rf"\.{class_name}\s*\{{([^}}]+)}}", css)
            self.assertIsNotNone(rule, class_name)
            background_match = re.search(r"background:\s*(#[0-9a-f]{6}|var\(--color-[\w-]+\))", rule.group(1))
            self.assertIsNotNone(background_match, class_name)
            background = background_match.group(1)
            if background.startswith("var("):
                background = tokens[background.removeprefix("var(--color-").removesuffix(")")]
            with self.subTest(status=class_name):
                self.assertGreaterEqual(_contrast_ratio(foreground, background), 4.5)

    def test_non_text_status_markers_have_visible_edge_and_labels_stay_readable(self) -> None:
        css = Path("app/static/css/tailwind.input.css").read_text(encoding="utf-8").lower()
        theme = css.split("@font-face", maxsplit=1)[0]
        tokens = dict(re.findall(r"--color-([\w-]+):\s*(#[0-9a-f]{6})", theme))
        # The calendar legend dot is a non-text graphical object (WCAG 1.4.11) and
        # must carry a visible border, not only a pale tint fill.
        dot_rule = re.search(r"\.attendance-dot\s*\{([^}}]+)\}", css)
        self.assertIsNotNone(dot_rule)
        self.assertRegex(dot_rule.group(1), r"border:\s*1px solid rgba\(\s*48\s*,\s*48\s*,\s*68\s*,\s*\.(\d+)\)")
        alpha = float(re.search(r"\.(\d+)\)", dot_rule.group(1)).group(1))
        self.assertGreaterEqual(alpha, 0.6)
        # Danger and warning text must clear 4.5:1 on their badge tints.
        for foreground, background in (
            (tokens["danger"], "#fde5e3"),
            (tokens["warning"], "#fff5df"),
        ):
            with self.subTest(foreground=foreground):
                self.assertGreaterEqual(_contrast_ratio(foreground, background), 4.5)
        # Uppercase micro-labels must not fall below 13px for legibility.
        eyebrow = re.search(r"\.eyebrow\s*\{([^}}]+)\}", css).group(1)
        size = re.search(r"font-size:\s*([\d.]+)rem", eyebrow)
        self.assertIsNotNone(size)
        self.assertGreaterEqual(float(size.group(1)) * 16, 13)

    def test_role_illustrations_are_local_and_success_waits_for_server_confirmation(self) -> None:
        teacher = Path("app/templates/teacher/dashboard.html").read_text(encoding="utf-8")
        enrollment = Path("app/templates/student/enrollment.html").read_text(encoding="utf-8")
        script = Path("app/static/js/face-enrollment.js").read_text(encoding="utf-8")
        self.assertIn("illustrations/teacher-welcome-v2.webp", teacher)
        self.assertIn('class="teacher-welcome-art"', teacher)
        self.assertIn("illustrations/enrollment-v2.webp", enrollment)
        self.assertIn("data-success-illustration-url=", enrollment)
        self.assertIn('if (result.enrollment_complete)', script)
        self.assertIn("enrollmentIllustration.src = successIllustrationUrl", script)
        self.assertIn("model wajah telah diperbarui", script)

    def test_student_redesign_preserves_camera_and_recovery_dom_contract(self) -> None:
        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = {}
            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if attributes.get('id'):
                    self.ids.setdefault(attributes['id'], []).append(attributes)
        page = Elements()
        page.feed(self.get_as('student', '/student/dashboard').get_data(as_text=True))
        required = ('attendance-today', 'attendance-cta', 'attendance-status',
                    'attendance-refresh', 'attendance-camera-panel', 'attendance-video',
                    'attendance-placeholder', 'attendance-cancel', 'attendance-location-help',
                    'attendance-checkin-time', 'attendance-checkout-time',
                    'attendance-schedule-times', 'attendance-status-label')
        for element_id in required:
            with self.subTest(element_id=element_id):
                self.assertEqual(len(page.ids.get(element_id, [])), 1)
        self.assertEqual(page.ids['attendance-cta'][0]['data-cta-action'], 'checkin')
        self.assertIn('hidden', page.ids['attendance-camera-panel'][0])
        for attribute in ('data-csrf', 'data-state-url', 'data-start-url', 'data-frame-url',
                          'data-checkout-start-url', 'data-checkout-frame-url'):
            self.assertTrue(page.ids['attendance-today'][0][attribute])


if __name__ == "__main__":
    unittest.main()
