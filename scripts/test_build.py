import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import build


class IconValidation(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="hexaza-check-")
        self.addCleanup(self.work.cleanup)
        self.pack = Path(self.work.name) / build.PACK.name
        shutil.copytree(build.PACK, self.pack)
        self.patch = patch.object(build, "PACK", self.pack)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_accepts_current_sources(self):
        expected = json.loads((self.pack / "manifest.json").read_text())["Version"]
        manifest, entries = build.check_sources("v" + expected)
        self.assertEqual(manifest["Version"], expected)
        self.assertEqual(len(entries), 6)

    def test_rejects_wrong_tag(self):
        with self.assertRaisesRegex(ValueError, "버전"):
            build.check_sources("v0.0.0")

    def test_rejects_duplicate_icon(self):
        index = self.pack / "icons.json"
        entries = json.loads(index.read_text())
        entries[-1] = entries[0]
        index.write_text(json.dumps(entries))
        with self.assertRaisesRegex(ValueError, "누락·중복"):
            build.check_sources()

    def test_rejects_wrong_image_size(self):
        from PIL import Image
        Image.new("RGB", (72, 72)).save(self.pack / "icons" / "melon.png")
        with self.assertRaisesRegex(ValueError, "144"):
            build.check_sources()


    def preview_fixture(self, wrong_pixel=False):
        from PIL import Image
        documented = (build.ROOT / "docs" / "preview.png").read_bytes()
        root = Path(self.work.name)
        (root / "docs").mkdir()
        (root / "docs" / "preview.png").write_bytes(documented)
        with Image.open(io.BytesIO(documented)) as image:
            image = image.convert("RGB")
            if wrong_pixel:
                image.putpixel((0, 0), (255, 0, 255))
            output = io.BytesIO()
            image.save(output, format="PNG", compress_level=0)
        return root, documented, output.getvalue()

    def test_accepts_equivalent_png_compression_and_ships_documented_bytes(self):
        root, documented, alternate = self.preview_fixture()
        self.assertNotEqual(documented, alternate)
        with patch.object(build, "ROOT", root), patch.object(build, "preview", return_value=alternate), patch("sys.argv", ["build.py"]):
            build.main()
        self.assertEqual((root / "dist" / "preview.png").read_bytes(), documented)

    def test_rejects_changed_preview_pixels(self):
        root, documented, altered = self.preview_fixture(wrong_pixel=True)
        with patch.object(build, "ROOT", root), patch.object(build, "preview", return_value=altered), patch("sys.argv", ["build.py"]):
            with self.assertRaisesRegex(ValueError, "미리보기"):
                build.main()


    def test_package_is_deterministic_without_platform_compression(self):
        root = Path(self.work.name)
        first, second = root / "first.zip", root / "second.zip"
        with patch.object(build, "ROOT", root):
            build.package(first)
            build.package(second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with zipfile.ZipFile(first) as archive:
            self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
            self.assertTrue(all(info.date_time == (2026, 1, 1, 0, 0, 0) for info in archive.infolist()))


if __name__ == "__main__":
    unittest.main()
