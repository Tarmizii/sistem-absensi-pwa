"""PWA entry points expose a local manifest and root-scoped worker (T30)."""

from __future__ import annotations

import json
import re
import unittest
from io import BytesIO

from PIL import Image
from app import create_app


class PwaRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "pwa-test"})
        self.client = self.app.test_client()

    def test_public_entry_page_links_local_manifest_and_registration_script(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('rel="manifest"', body)
        self.assertIn("/static/manifest.webmanifest", body)
        self.assertIn("/static/js/pwa-register.js", body)
        response.close()

    def test_manifest_has_authentication_start_url_and_installable_local_icons(self):
        response = self.client.get("/static/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        manifest = json.loads(response.get_data(as_text=True))
        self.assertEqual(manifest["start_url"], "/login?source=pwa")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["background_color"], "#FFF5E3")
        self.assertEqual(manifest["theme_color"], "#FFF5E3")
        sizes = {icon["sizes"] for icon in manifest["icons"]}
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)
        for icon in manifest["icons"]:
            image = self.client.get(icon["src"])
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.mimetype, "image/png")
            self.assertTrue(image.data.startswith(b"\x89PNG\r\n\x1a\n"))
            dimensions = (int.from_bytes(image.data[16:20], "big"), int.from_bytes(image.data[20:24], "big"))
            self.assertEqual(dimensions, tuple(map(int, icon["sizes"].split("x"))))
            image.close()
        response.close()

    def test_product_illustrations_are_local_and_within_delivery_budget(self):
        total = 0
        for name in ("welcome", "attendance", "enrollment", "success", "school-day", "teacher-welcome", "admin-welcome"):
            with self.subTest(name=name):
                response = self.client.get(f"/static/illustrations/{name}-v2.webp")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "image/webp")
                self.assertEqual(response.data[:4], b"RIFF")
                self.assertEqual(response.data[8:12], b"WEBP")
                self.assertLessEqual(len(response.data), 200_000)
                total += len(response.data)
                response.close()
        self.assertLessEqual(total, 1_500_000)
        # These two originals remain usable until imagegen quota allows v2.
        for name in ("location", "empty"):
            with self.subTest(name=name):
                response = self.client.get(f"/static/illustrations/{name}.svg")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "image/svg+xml")
                self.assertIn("<svg", response.get_data(as_text=True))
                response.close()

    def test_plus_jakarta_font_and_open_font_license_are_public_local_assets(self):
        font = self.client.get("/static/fonts/plus-jakarta-sans-variable.ttf")
        self.assertEqual(font.status_code, 200)
        self.assertTrue(font.data.startswith(b"\x00\x01\x00\x00"))
        font.close()

        license_response = self.client.get("/static/fonts/OFL.txt")
        self.assertEqual(license_response.status_code, 200)
        self.assertIn("SIL OPEN FONT LICENSE", license_response.get_data(as_text=True))
        license_response.close()

    def test_service_worker_is_root_scoped_and_script_is_public(self):
        response = self.client.get("/service-worker.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Service-Worker-Allowed"], "/")
        self.assertIn("no-cache", response.headers["Cache-Control"])
        self.assertIn("addEventListener(\"fetch\"", response.get_data(as_text=True))
        response.close()

    def test_generic_offline_document_is_public_and_contains_no_personal_data(self):
        response = self.client.get("/static/offline.html")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True).lower()
        self.assertIn("sedang offline", body)
        self.assertIn("/", body)
        for sensitive in ("nisn", "attendance_records", "face_registered", "latitude", "password"):
            self.assertNotIn(sensitive, body)
        response.close()


class PrecacheBudgetTests(unittest.TestCase):
    """The offline shell ships to students on school networks; keep it small (B1)."""

    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "precache-test"})
        self.client = self.app.test_client()
        response = self.client.get("/service-worker.js")
        self.worker = response.get_data(as_text=True)
        response.close()
        self.paths = re.findall(r'"(/static/[^"]+)"', self.worker)

    def test_every_precached_url_resolves(self):
        self.assertTrue(self.paths, "service worker should precache the public shell")
        for path in self.paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, f"{path} is precached but missing")
                response.close()

    def test_precache_payload_stays_within_budget(self):
        total = 0
        for path in self.paths:
            response = self.client.get(path)
            total += len(response.data)
            response.close()
        self.assertLessEqual(total, 700_000, f"precache is {total} bytes")

    def test_precached_illustrations_are_not_oversized_for_their_render_size(self):
        # Illustrations render at 12-25rem; anything beyond 800px is wasted bytes.
        for path in self.paths:
            if not path.endswith(".webp"):
                continue
            with self.subTest(path=path):
                response = self.client.get(path)
                with Image.open(BytesIO(response.data)) as image:
                    self.assertLessEqual(image.size[0], 800)
                response.close()


class ServiceWorkerResilienceTests(unittest.TestCase):
    """One broken asset must not void the whole offline shell (B2)."""

    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "sw-test"})
        self.client = self.app.test_client()
        response = self.client.get("/service-worker.js")
        self.worker = response.get_data(as_text=True)
        response.close()

    def test_precache_is_per_asset_tolerant_not_atomic(self):
        self.assertIn("Promise.allSettled", self.worker)
        self.assertNotIn("cache.addAll(", self.worker)

    def test_private_routes_are_excluded_from_caching(self):
        self.assertIn("isPrivatePath", self.worker)
        block = re.search(
            r"NEVER_CACHE_PATTERNS\s*=\s*\[(.*?)\]", self.worker, re.S
        )
        self.assertIsNotNone(block, "worker should declare NEVER_CACHE_PATTERNS")
        patterns = block.group(1)
        for segment in ("attendance", "face", "admin", "student", "teacher", "evidence", "logout"):
            with self.subTest(segment=segment):
                self.assertIn(segment, patterns)

    def test_install_and_update_affordances_exist_for_students_only(self):
        response = self.client.get("/static/js/pwa-register.js")
        register = response.get_data(as_text=True)
        response.close()
        self.assertIn("beforeinstallprompt", register)
        self.assertIn("student-shell", register)
        self.assertIn("updatefound", register)


class ManifestMetadataTests(unittest.TestCase):
    """A manifest without lang/dir/orientation ships incomplete metadata (B3)."""

    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "manifest-test"})
        self.client = self.app.test_client()

    def test_manifest_declares_language_direction_and_orientation(self):
        response = self.client.get("/static/manifest.webmanifest")
        manifest = json.loads(response.get_data(as_text=True))
        response.close()
        self.assertEqual(manifest["lang"], "id")
        self.assertEqual(manifest["dir"], "ltr")
        self.assertEqual(manifest["orientation"], "portrait-primary")
        self.assertIn("id", manifest)

    def test_apple_touch_icon_is_served_at_its_declared_size(self):
        body_response = self.client.get("/login")
        body = body_response.get_data(as_text=True)
        body_response.close()
        self.assertIn('sizes="180x180"', body)
        response = self.client.get("/static/icons/apple-touch-icon.png")
        self.assertEqual(response.status_code, 200)
        dimensions = (
            int.from_bytes(response.data[16:20], "big"),
            int.from_bytes(response.data[20:24], "big"),
        )
        self.assertEqual(dimensions, (180, 180))
        response.close()


if __name__ == "__main__":
    unittest.main()
