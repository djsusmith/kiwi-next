#!/usr/bin/env python3
"""Idempotent patcher that ports Kiwi Browser features onto Chromium 160+ Android."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


def _patch_text(path: Path, marker: str, pattern: str, replacement: str, label: str) -> str:
    """Apply a regex/substring replacement once; return 'applied' or 'already'."""
    content = path.read_text(encoding="utf-8")
    if marker in content:
        return f"already:{label}"
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Failed to patch {label} in {path}: pattern not found")
    path.write_text(updated, encoding="utf-8")
    return f"applied:{label}"


def patch_toolbar_phone(chromium_src: Path) -> str:
    """Add extensions_toolbar_container_stub to phone toolbar layout."""
    target = chromium_src / "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml"
    marker = "extensions_toolbar_container_stub"
    stub_xml = (
        '        <ViewStub\n'
        '            android:id="@+id/extensions_toolbar_container_stub"\n'
        '            android:inflatedId="@+id/extensions_toolbar_container"\n'
        '            android:layout_width="wrap_content"\n'
        '            android:layout_height="?attr/toolbarButtonHeight"\n'
        '            android:layout_marginVertical="?attr/toolbarButtonMarginVertical"/>\n\n'
        '        <org.chromium.chrome.browser.toolbar.top.ToggleTabStackButton'
    )
    return _patch_text(
        target,
        marker,
        r'        <org\.chromium\.chrome\.browser\.toolbar\.top\.ToggleTabStackButton',
        stub_xml,
        "toolbar_phone_extensions_stub",
    )


def patch_app_menu_delegate_impl(chromium_src: Path) -> list[str]:
    """Expose Manage Extensions and Chrome Web Store builders to phone menu."""
    target = (
        chromium_src
        / "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java"
    )
    results = []
    results.append(
        _patch_text(
            target,
            "protected ListItem buildManageExtensionsItem()",
            r"private ListItem buildManageExtensionsItem\(\)\s*\{\s*assert shouldShowExtensionsItem\(\);\s*//[^\n]*\n\s*//[^\n]*\n\s*assert isSubmenusEnabled\(mContext\);",
            "protected ListItem buildManageExtensionsItem() {\n        assert shouldShowExtensionsItem();",
            "app_menu_manage_extensions_visibility",
        )
    )
    results.append(
        _patch_text(
            target,
            "protected ListItem buildChromeWebstoreItem()",
            r"private ListItem buildChromeWebstoreItem\(\)",
            "protected ListItem buildChromeWebstoreItem()",
            "app_menu_webstore_visibility",
        )
    )
    return results


def patch_tabbed_app_menu(chromium_src: Path) -> str:
    """Add Manage Extensions, Chrome Web Store, and DevTools to phone app menu."""
    target = (
        chromium_src
        / "chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java"
    )
    marker = "Kiwi Next: expose Manage Extensions, Web Store & DevTools on phones"
    replacement = (
        "        // Extensions (Kiwi Next: expose Manage Extensions, Web Store & DevTools on phones)\n"
        "        if (shouldShowExtensionsItem()) {\n"
        "            modelList.add(buildExtensionsMenuItem(shouldShowIconBeforeItem));\n"
        "            modelList.add(buildManageExtensionsItem());\n"
        "            modelList.add(buildChromeWebstoreItem());\n"
        "        }\n"
        "        if (mMoreToolsItemBuilder.shouldShowDevToolsItem(currentTab)) {\n"
        "            modelList.add(mMoreToolsItemBuilder.buildDevToolsItem());\n"
        "        }"
    )
    return _patch_text(
        target,
        marker,
        r"        // Extensions\n        if \(shouldShowExtensionsItem\(\)\) \{\n            modelList\.add\(buildExtensionsMenuItem\(shouldShowIconBeforeItem\)\);\n        \}",
        replacement,
        "tabbed_app_menu_phone_kiwi_items",
    )


def patch_chrome_tabbed_activity(chromium_src: Path) -> str:
    """Guard extensions_menu_menu_id against null coordinator by opening chrome://extensions."""
    target = (
        chromium_src
        / "chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java"
    )
    marker = "Kiwi Next null-safe fallback to chrome://extensions"
    replacement = (
        "        } else if (id == R.id.extensions_menu_menu_id) {\n"
        "            // Kiwi Next null-safe fallback to chrome://extensions\n"
        "            ExtensionsToolbarCoordinator coordinator =\n"
        "                    getToolbarManager() != null ? getToolbarManager().getExtensionsToolbarCoordinator() : null;\n"
        "            if (coordinator != null) {\n"
        "                coordinator.showExtensionsMenu();\n"
        "            } else {\n"
        "                LoadUrlParams params = new LoadUrlParams(\n"
        "                        UrlConstants.CHROME_EXTENSIONS_URL, PageTransition.AUTO_TOPLEVEL);\n"
        "                getTabCreator(/* incognito= */ false)\n"
        "                        .createNewTab(params, TabLaunchType.FROM_CHROME_UI, currentTab);\n"
        "            }"
    )
    return _patch_text(
        target,
        marker,
        r"        \} else if \(id == R\.id\.extensions_menu_menu_id\) \{\n\s*ExtensionsToolbarCoordinator coordinator =\n\s*assumeNonNull\(getToolbarManager\(\)\)\.getExtensionsToolbarCoordinator\(\);\n\s*assumeNonNull\(coordinator\);\n\s*coordinator\.showExtensionsMenu\(\);",
        replacement,
        "chrome_tabbed_activity_extensions_fallback",
    )


def patch_dark_mode_amoled(chromium_src: Path) -> str:
    """Tune Blink dark mode foreground brightness threshold to Kiwi's AMOLED preset."""
    target = (
        chromium_src
        / "third_party/blink/renderer/platform/graphics/dark_mode_settings_builder.cc"
    )
    marker = "kDefaultForegroundBrightnessThreshold = 127;"
    return _patch_text(
        target,
        marker,
        r"const constexpr int kDefaultForegroundBrightnessThreshold = 150;",
        "const constexpr int kDefaultForegroundBrightnessThreshold = 127;",
        "blink_amoled_dark_mode_threshold",
    )


def patch_current_channel_logo(chromium_src: Path) -> str:
    """Prevent CHECK_IS_TEST() crash on dev/beta/stable channels without Google branding."""
    target = chromium_src / "chrome/browser/ui/webui/current_channel_logo.cc"
    marker = "Kiwi Next: allow non-Google-branded channels"
    return _patch_text(
        target,
        marker,
        r"    case version_info::Channel::STABLE:\n      CHECK_IS_TEST\(\);\n      \[\[fallthrough\]\];",
        "    case version_info::Channel::STABLE:\n      // Kiwi Next: allow non-Google-branded channels\n      [[fallthrough]];",
        "current_channel_logo_no_test_check",
    )


def patch_devtools_android(chromium_src: Path) -> list[str]:
    """Enable Android DevTools frontend feature and allow it on phones."""
    results = []
    features_cc = chromium_src / "content/public/common/content_features.cc"
    results.append(
        _patch_text(
            features_cc,
            "BASE_FEATURE(kAndroidDevToolsFrontend, base::FEATURE_ENABLED_BY_DEFAULT);",
            r"BASE_FEATURE\(kAndroidDevToolsFrontend, base::FEATURE_DISABLED_BY_DEFAULT\);",
            "BASE_FEATURE(kAndroidDevToolsFrontend, base::FEATURE_ENABLED_BY_DEFAULT);",
            "enable_android_devtools_frontend_flag",
        )
    )
    devtools_java = (
        chromium_src
        / "chrome/browser/devtools/android/java/src/org/chromium/chrome/browser/devtools/DevToolsWindowAndroid.java"
    )
    results.append(
        _patch_text(
            devtools_java,
            "Kiwi Next: allow DevTools on phones",
            r"return ContentFeatureMap\.isEnabled\(ContentFeatureList\.ANDROID_DEV_TOOLS_FRONTEND\)\s*\n\s*&& DeviceFormFactor\.isNonMultiDisplayContextOnTablet\(context\);",
            "// Kiwi Next: allow DevTools on phones\n        return ContentFeatureMap.isEnabled(ContentFeatureList.ANDROID_DEV_TOOLS_FRONTEND);",
            "devtools_window_allow_phones",
        )
    )
    return results


def patch_toolbar_manager(chromium_src: Path) -> str:
    """Fix ClassCastException on phones by replacing (ToolbarTablet) cast with ViewGroup."""
    target = (
        chromium_src
        / "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java"
    )
    marker = "(ViewGroup) mToolbarLayout"
    return _patch_text(
        target,
        marker,
        r"\(ToolbarTablet\) mToolbarLayout,",
        "(ViewGroup) mToolbarLayout,",
        "toolbar_manager_phone_root_view_cast",
    )


def patch_branding(chromium_src: Path, overlay_root: Path) -> list[str]:
    """Overlay Kiwi icons and update Chromium product name strings to Kiwi Next."""
    results = []
    strings_grd = chromium_src / "chrome/app/chromium_strings.grd"
    if strings_grd.exists():
        content = strings_grd.read_text(encoding="utf-8")
        if "Kiwi Next" not in content:
            updated = re.sub(
                r'(<message name="IDS_(?:SHORT_)?PRODUCT_NAME"[^>]*>\s*)Chromium(\s*</message>)',
                r"\1Kiwi Next\2",
                content,
            )
            strings_grd.write_text(updated, encoding="utf-8")
            results.append("applied:product_name_strings")
        else:
            results.append("already:product_name_strings")

    for res_dir in ("res_chromium_base", "res_chromium"):
        src_dir = overlay_root / "chrome/android/java" / res_dir
        dst_dir = chromium_src / "chrome/android/java" / res_dir
        if src_dir.exists() and dst_dir.exists() and src_dir.resolve() != dst_dir.resolve():
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            for mipmap_dir in dst_dir.glob("mipmap-*"):
                fg = mipmap_dir / "ic_foreground.png"
                bg = mipmap_dir / "ic_background.png"
                if fg.exists():
                    shutil.copy2(fg, mipmap_dir / "layered_app_icon.png")
                if bg.exists():
                    shutil.copy2(bg, mipmap_dir / "layered_app_icon_background.png")
            results.append(f"applied:icons_{res_dir}")
        else:
            results.append(f"already:icons_{res_dir}")

    channel_constants = (
        chromium_src
        / "chrome/android/java/res_chromium_base/values/channel_constants.xml"
    )
    if channel_constants.exists():
        content = channel_constants.read_text(encoding="utf-8")
        if "Kiwi Next" not in content:
            updated = re.sub(
                r'<string name="app_name"[^>]*>[^<]+</string>',
                '<string name="app_name" translatable="false">Kiwi Next</string>',
                content,
            )
            channel_constants.write_text(updated, encoding="utf-8")
            results.append("applied:channel_constants_app_name")
        else:
            results.append("already:channel_constants_app_name")
    return results


def apply_all(chromium_src: Path, overlay_root: Path) -> list[str]:
    """Apply all Kiwi-on-Chromium-160 patches cleanly."""
    results: list[str] = []
    results.append(patch_toolbar_phone(chromium_src))
    results.append(patch_toolbar_manager(chromium_src))
    results.extend(patch_app_menu_delegate_impl(chromium_src))
    results.append(patch_tabbed_app_menu(chromium_src))
    results.append(patch_chrome_tabbed_activity(chromium_src))
    results.append(patch_dark_mode_amoled(chromium_src))
    results.append(patch_current_channel_logo(chromium_src))
    results.extend(patch_devtools_android(chromium_src))
    results.extend(patch_branding(chromium_src, overlay_root))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Port Kiwi Browser patches onto Chromium 160")
    parser.add_argument("--chromium-src", required=True, type=Path, help="Path to Chromium src/")
    parser.add_argument(
        "--overlay-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to kiwi-next overlay root",
    )
    args = parser.parse_args(argv)
    results = apply_all(args.chromium_src, args.overlay_root)
    for item in results:
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
