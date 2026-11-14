import json
import unittest
from pathlib import Path

EXT_DIR = Path(__file__).resolve().parent.parent / "extensions/kiwi_mcp_bridge"


class TestMcpBridgeManifest(unittest.TestCase):
    def test_manifest_mv3_valid(self):
        manifest = json.loads((EXT_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("tabs", manifest["permissions"])
        self.assertIn("scripting", manifest["permissions"])
        self.assertIn("activeTab", manifest["permissions"])
        self.assertEqual(manifest["background"]["service_worker"], "background.js")

    def test_extension_files_exist(self):
        for fname in ("background.js", "popup.html", "popup.js"):
            self.assertTrue((EXT_DIR / fname).is_file(), f"Missing {fname}")


if __name__ == "__main__":
    unittest.main()
