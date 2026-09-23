"""Private storage boundaries with synthetic images only."""

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, PngImagePlugin

from app import create_app
from app.services.storage_service import (
    MAX_IMAGE_BYTES, StorageError, init_storage, resolve_private_file,
    save_camera_image, save_trained_model, validate_camera_image,
)


def picture(fmt="PNG", size=(32, 24)):
    stream = BytesIO()
    Image.new("RGB", size, (120, 80, 200)).save(stream, format=fmt)
    return stream.getvalue()


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private"
        self.app = create_app({"TESTING": True, "SECRET_KEY": "storage-test",
                               "STORAGE_ROOT": str(self.root)})
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)

    def test_images_roundtrip_with_random_names_and_metadata_removed(self):
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("sensitive-location", "synthetic-metadata")
        stream = BytesIO()
        Image.new("RGB", (32, 24)).save(stream, format="PNG", pnginfo=metadata)
        for fmt, mime, data in (("PNG", "image/png", stream.getvalue()),
                                ("JPEG", "image/jpeg", picture("JPEG"))):
            with self.subTest(fmt=fmt):
                key = save_camera_image("faces", data, mime)
                other = save_camera_image("faces", data, mime)
                self.assertNotEqual(key, other)
                with Image.open(resolve_private_file(key)) as result:
                    self.assertEqual(result.size, (32, 24))
                    self.assertEqual(result.format, "PNG")
                    self.assertEqual(result.info, {})

    def test_invalid_payloads_rejected_before_write(self):
        cases = [(b"", "image/png"), (b"html", "image/png"),
                 (picture(), "image/jpeg"), (picture(), "image/svg+xml"),
                 (picture()[:40], "image/png"),
                 (b"x" * (MAX_IMAGE_BYTES + 1), "image/png"),
                 (picture(size=(4097, 1)), "image/png")]
        for payload, mime in cases:
            with self.subTest(mime=mime, length=len(payload)), self.assertRaises(StorageError):
                save_camera_image("faces", payload, mime)
        self.assertEqual(list((self.root / "faces").iterdir()), [])

    def test_pixel_limit_checked_before_full_decode(self):
        data = picture(size=(3000, 3000))
        with patch("PIL.PngImagePlugin.PngImageFile.load", side_effect=AssertionError("must not decode")):
            with self.assertRaises(StorageError):
                validate_camera_image(data, "image/png")

    def test_path_traversal_absolute_paths_and_wrong_categories_rejected(self):
        for key in ("../secret", "faces/../../secret", "C:/private/file.png",
                    "/etc/passwd", "faces\\" + "a" * 32 + ".png",
                    "faces/%2e%2e/secret", "faces/a.png:stream", "models/x.png"):
            with self.subTest(key=key), self.assertRaises(StorageError):
                resolve_private_file(key)
        with self.assertRaises(StorageError):
            save_camera_image("../static", picture(), "image/png")

    def test_private_files_have_no_public_http_route(self):
        key = save_camera_image("attendance", picture(), "image/png")
        self.assertTrue(resolve_private_file(key).is_file())
        client = self.app.test_client()
        for url in (f"/storage/{key}", f"/static/{key}", f"/static/../storage/{key}"):
            response = client.get(url)
            self.assertEqual(response.status_code, 404)
            response.close()

    def test_static_storage_configuration_rejected(self):
        self.app.config["STORAGE_ROOT"] = str(Path(self.app.static_folder) / "private")
        with self.assertRaises(StorageError):
            init_storage()

    def test_resolved_link_escape_rejected(self):
        # Simulate the path resolver after an OS symlink/junction. No Windows
        # administrator privilege is required to exercise the rejection.
        key = save_camera_image("faces", picture(), "image/png")
        original = Path.resolve
        path = self.root / key
        def resolve(candidate, *args, **kwargs):
            return Path(self.temp.name) / "outside.png" if candidate == path else original(candidate, *args, **kwargs)
        with patch.object(Path, "resolve", resolve), self.assertRaises(StorageError):
            resolve_private_file(key)

    def test_write_failure_removes_partial_file(self):
        with patch("app.services.storage_service.os.fsync", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                save_camera_image("faces", picture(), "image/png")
        self.assertEqual(list((self.root / "faces").iterdir()), [])

    def test_server_model_storage_and_missing_file(self):
        data = b"%YAML:1.0\nsynthetic: 1\n"
        key = save_trained_model(data)
        self.assertEqual(resolve_private_file(key).read_bytes(), data)
        with self.assertRaises(StorageError):
            save_trained_model(b"")
        with self.assertRaises(FileNotFoundError):
            resolve_private_file("faces/" + "0" * 32 + ".png")
