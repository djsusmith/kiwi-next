import tempfile
import unittest
from pathlib import Path

from scripts.apply_kiwi_160_patches import apply_all


class TestApplyKiwi160Patches(unittest.TestCase):
    def _create_mock_chromium(self, root: Path) -> None:
        toolbar = root / "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml"
        toolbar.parent.mkdir(parents=True, exist_ok=True)
        toolbar.write_text(
            "<LinearLayout>\n"
            "        <org.chromium.chrome.browser.toolbar.top.ToggleTabStackButton\n"
            "            android:id=\"@+id/tab_switcher_button\"/>\n"
            "</LinearLayout>\n",
            encoding="utf-8",
        )

        app_menu = (
            root
            / "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java"
        )
        app_menu.parent.mkdir(parents=True, exist_ok=True)
        app_menu.write_text(
            "    private ListItem buildManageExtensionsItem() {\n"
            "        assert shouldShowExtensionsItem();\n\n"
            "        // The id is used for both.\n"
            "        // disabled in different context.\n"
            "        assert isSubmenusEnabled(mContext);\n"
            "        return null;\n"
            "    }\n"
            "    private ListItem buildChromeWebstoreItem() {\n"
            "        return null;\n"
            "    }\n",
            encoding="utf-8",
        )

        tabbed_menu = (
            root
            / "chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java"
        )
        tabbed_menu.parent.mkdir(parents=True, exist_ok=True)
        tabbed_menu.write_text(
            "        // Extensions\n"
            "        if (shouldShowExtensionsItem()) {\n"
            "            modelList.add(buildExtensionsMenuItem(shouldShowIconBeforeItem));\n"
            "        }\n",
            encoding="utf-8",
        )

        tabbed_activity = (
            root
            / "chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java"
        )
        tabbed_activity.parent.mkdir(parents=True, exist_ok=True)
        tabbed_activity.write_text(
            "        } else if (id == R.id.extensions_menu_menu_id) {\n"
            "            ExtensionsToolbarCoordinator coordinator =\n"
            "                    assumeNonNull(getToolbarManager()).getExtensionsToolbarCoordinator();\n"
            "            assumeNonNull(coordinator);\n"
            "            coordinator.showExtensionsMenu();\n"
            "        }\n",
            encoding="utf-8",
        )

        dark_mode = (
            root / "third_party/blink/renderer/platform/graphics/dark_mode_settings_builder.cc"
        )
        dark_mode.parent.mkdir(parents=True, exist_ok=True)
        dark_mode.write_text(
            "const constexpr int kDefaultForegroundBrightnessThreshold = 150;\n",
            encoding="utf-8",
        )

        grd = root / "chrome/app/chromium_strings.grd"
        grd.parent.mkdir(parents=True, exist_ok=True)
        grd.write_text(
            '<message name="IDS_SHORT_PRODUCT_NAME" desc="short">Chromium</message>\n'
            '<message name="IDS_PRODUCT_NAME" desc="full">Chromium</message>\n',
            encoding="utf-8",
        )

        (root / "chrome/android/java/res_chromium_base/mipmap-xxxhdpi").mkdir(
            parents=True, exist_ok=True
        )

    def test_apply_all_and_idempotency(self) -> None:
        overlay_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            chromium_src = Path(tmp)
            self._create_mock_chromium(chromium_src)

            first = apply_all(chromium_src, overlay_root)
            self.assertTrue(any(r.startswith("applied:") for r in first))

            toolbar_text = (
                chromium_src
                / "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml"
            ).read_text(encoding="utf-8")
            self.assertIn("extensions_toolbar_container_stub", toolbar_text)

            tabbed_text = (
                chromium_src
                / "chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java"
            ).read_text(encoding="utf-8")
            self.assertIn("buildManageExtensionsItem()", tabbed_text)
            self.assertIn("buildChromeWebstoreItem()", tabbed_text)
            self.assertIn("buildDevToolsItem()", tabbed_text)

            grd_text = (chromium_src / "chrome/app/chromium_strings.grd").read_text(
                encoding="utf-8"
            )
            self.assertIn(">Kiwi Next<", grd_text)

            # Second run must be idempotent
            second = apply_all(chromium_src, overlay_root)
            self.assertIn("already:toolbar_phone_extensions_stub", second)
            self.assertIn("already:tabbed_app_menu_phone_kiwi_items", second)
            self.assertIn("already:product_name_strings", second)


if __name__ == "__main__":
    unittest.main()
