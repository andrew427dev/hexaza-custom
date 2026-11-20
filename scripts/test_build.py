import json
from pathlib import Path
import shutil
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
