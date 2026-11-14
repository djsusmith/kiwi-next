import unittest
from pathlib import Path
from scripts.audit_chromium_overlay import parse_version_file, audit_overlay

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestAuditChromiumOverlay(unittest.TestCase):
    def test_chromium_version_is_159(self):
        ver = parse_version_file(REPO_ROOT / "CHROMIUM_VERSION")
        self.assertEqual(ver["CHROMIUM_MAJOR"], "159")
        self.assertEqual(ver["CHROMIUM_MINOR"], "0")
        self.assertEqual(ver["CHROMIUM_BUILD"], "8144")
        self.assertEqual(ver["CHROMIUM_PATCH"], "0")

    def test_kiwi_version_is_159(self):
        ver = parse_version_file(REPO_ROOT / "KIWI_VERSION")
        self.assertEqual(ver["MAJOR"], "159")
        self.assertEqual(ver["BUILD"], "8144")

    def test_audit_overlay_counts_modified_dirs(self):
        report = audit_overlay(REPO_ROOT)
        self.assertIn("chrome", report["top_level_dirs"])
        self.assertIn("extensions", report["top_level_dirs"])
        self.assertGreater(report["total_files"], 100)


if __name__ == "__main__":
    unittest.main()
