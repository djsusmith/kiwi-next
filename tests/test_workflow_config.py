import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestWorkflowConfig(unittest.TestCase):
    def test_build_apk_workflow_no_dead_server(self):
        content = (REPO_ROOT / ".github/workflows/build_apk.yml").read_text(encoding="utf-8")
        self.assertNotIn("longbuild.find.kiwi", content)
        self.assertNotIn("build.find.kiwi", content)
        self.assertIn("autoninja", content)
        self.assertIn("chrome_public_apk", content)
        self.assertIn("CHROMIUM_VERSION", content)

    def test_chromium_159_args_gn(self):
        gn = (REPO_ROOT / ".build/chromium_159/args.gn").read_text(encoding="utf-8")
        self.assertIn('target_os = "android"', gn)
        self.assertIn('target_cpu = "arm64"', gn)
        self.assertIn("is_desktop_android = true", gn)
        self.assertIn("enable_desktop_android_extensions = true", gn)
        self.assertIn('chrome_public_manifest_package = "com.kiwibrowser.next"', gn)


if __name__ == "__main__":
    unittest.main()
