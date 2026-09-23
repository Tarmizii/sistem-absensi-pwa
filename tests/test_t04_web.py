import re
import unittest

from scripts.t04_web import create_poc_app


class T04WebPocTests(unittest.TestCase):
    def setUp(self):
        self.client = create_poc_app("kode-uji", testing=True).test_client()

    @staticmethod
    def csrf(response):
        match = re.search(r'data-csrf="([^"]+)"', response.get_data(as_text=True))
        assert match
        return match.group(1)

    def test_unlock_starts_isolated_session_and_reset_does_not_touch_database(self):
        landing = self.client.get("/")
        token = self.csrf(landing)
        self.assertEqual(
            self.client.post("/unlock", data={"csrf_token": token, "access_code": "kode-uji"}).status_code,
            302,
        )
        active = self.client.get("/")
        self.assertIn("Nyalakan kamera", active.get_data(as_text=True))
        active_token = self.csrf(active)
        reset = self.client.post("/api/reset", headers={"X-CSRF-Token": active_token})
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.get_json()["poses"], [])

    def test_invalid_code_and_expired_session_are_rejected(self):
        landing = self.client.get("/")
        token = self.csrf(landing)
        self.assertEqual(
            self.client.post("/unlock", data={"csrf_token": token, "access_code": "salah"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/api/reset", headers={"X-CSRF-Token": token}).status_code,
            401,
        )

    def test_end_deletes_session_and_prevents_reuse(self):
        landing = self.client.get("/")
        token = self.csrf(landing)
        self.client.post("/unlock", data={"csrf_token": token, "access_code": "kode-uji"})
        active_token = self.csrf(self.client.get("/"))
        self.assertEqual(self.client.post("/api/end", headers={"X-CSRF-Token": active_token}).status_code, 200)
        self.assertEqual(self.client.post("/api/reset", headers={"X-CSRF-Token": active_token}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
