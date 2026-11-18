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


def patch_devtools_open_as_tab(chromium_src: Path) -> list[str]:
    """Open DevTools frontend as a regular browser tab instead of DevToolsActivity custom tab."""
    results = []
    devtools_window_cc = chromium_src / "chrome/browser/devtools/devtools_window.cc"
    if devtools_window_cc.exists():
        results.append(
            _patch_text(
                devtools_window_cc,
                "chrome/browser/ui/android/tab_model/tab_model_list.h",
                r'#include "chrome/android/chrome_jni_headers/DevToolsActivity_jni\.h"',
                '#include "chrome/android/chrome_jni_headers/DevToolsActivity_jni.h"\n'
                '#include "chrome/browser/ui/android/tab_model/tab_model.h"\n'
                '#include "chrome/browser/ui/android/tab_model/tab_model_list.h"\n'
                '#include "content/public/browser/android/child_process_importance.h"',
                "devtools_window_tab_model_includes",
            )
        )
        results.append(
            _patch_text(
                devtools_window_cc,
                "// Kiwi Next: open DevTools as a regular browser tab",
                r"#if BUILDFLAG\(IS_ANDROID\)\n"
                r"  if \(!owned_main_web_contents_ \|\| launched_activity_\) \{\n"
                r"    return;\n"
                r"  \}\n"
                r"  JNIEnv\* env = base::android::AttachCurrentThread\(\);\n"
                r"  Java_DevToolsActivity_launchDevToolsActivity\(\n"
                r"      env, main_web_contents_->GetJavaWebContents\(\)\);\n\n"
                r"  launched_activity_ = true;\n\n"
                r"  OverrideAndSyncDevToolsRendererPrefs\(\);",
                "#if BUILDFLAG(IS_ANDROID)\n"
                "  // Kiwi Next: open DevTools as a regular browser tab\n"
                "  if (!launched_activity_ && owned_main_web_contents_) {\n"
                "    TabModel* tab_model = nullptr;\n"
                "    if (content::WebContents* inspected = GetInspectedWebContents()) {\n"
                "      inspected->SetPrimaryPageImportance(\n"
                "          content::ChildProcessImportance::MODERATE,\n"
                "          content::ChildProcessImportance::NORMAL);\n"
                "      tab_model = TabModelList::GetTabModelForWebContents(inspected);\n"
                "    }\n"
                "    if (!tab_model && !TabModelList::models().empty()) {\n"
                "      tab_model = TabModelList::models().front();\n"
                "    }\n"
                "    if (tab_model) {\n"
                "      std::unique_ptr<content::WebContents> owned_web_contents =\n"
                "          OwnedMainWebContents::TakeWebContents(\n"
                "              std::move(owned_main_web_contents_));\n"
                "      if (owned_web_contents) {\n"
                "        int insert_index = tab_model->GetActiveIndex() + 1;\n"
                "        if (insert_index <= 0 || insert_index > tab_model->GetTabCount()) {\n"
                "          insert_index = tab_model->GetTabCount();\n"
                "        }\n"
                "        tabs::TabInterface* new_tab = tab_model->InsertWebContentsAt(\n"
                "            insert_index, std::move(owned_web_contents), false, std::nullopt);\n"
                "        if (new_tab) {\n"
                "          tab_model->ActivateTab(new_tab->GetHandle());\n"
                "        }\n"
                "        launched_activity_ = true;\n"
                "        OverrideAndSyncDevToolsRendererPrefs();\n"
                "      }\n"
                "    }\n"
                "  } else if (main_web_contents_ &&\n"
                "             action.type() != DevToolsToggleAction::kInspect) {\n"
                "    if (TabModel* tm =\n"
                "            TabModelList::GetTabModelForWebContents(main_web_contents_)) {\n"
                "      for (int i = 0; i < tm->GetTabCount(); ++i) {\n"
                "        if (tabs::TabInterface* t = tm->GetTab(i);\n"
                "            t && t->GetContents() == main_web_contents_) {\n"
                "          tm->ActivateTab(t->GetHandle());\n"
                "          break;\n"
                "        }\n"
                "      }\n"
                "    }\n"
                "  }",
                "devtools_window_open_in_tab_model",
            )
        )

    more_tools_java = (
        chromium_src
        / "chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/MoreToolsItemBuilder.java"
    )
    if more_tools_java.exists():
        results.append(
            _patch_text(
                more_tools_java,
                "Kiwi Next: allow DevTools menu item on native pages too",
                r"        if \(currentTab == null \|\| currentTab\.isNativePage\(\)\) \{\n"
                r"            return false;\n"
                r"        \}",
                "        // Kiwi Next: allow DevTools menu item on native pages too\n"
                "        if (currentTab == null) {\n"
                "            return false;\n"
                "        }\n"
                "        if (currentTab.isNativePage()) {\n"
                "            return DevToolsWindowAndroid.isDevToolsAvailable(mContext);\n"
                "        }",
                "more_tools_devtools_on_native_page",
            )
        )

    chrome_activity_java = (
        chromium_src
        / "chrome/android/java/src/org/chromium/chrome/browser/app/ChromeActivity.java"
    )
    if chrome_activity_java.exists():
        results.append(
            _patch_text(
                chrome_activity_java,
                "Kiwi Next: open chrome://inspect/#devices if on native page",
                r"        if \(id == R\.id\.dev_tools\n"
                r"                && DevToolsWindowAndroid\.isDevToolsAllowedFor\(\n"
                r"                        this, currentTab\.getProfile\(\), webContents\)\) \{\n"
                r"            DevToolsWindowAndroid\.openDevTools\(webContents\);",
                "        if (id == R.id.dev_tools && currentTab.isNativePage()) {\n"
                "            // Kiwi Next: open chrome://inspect/#devices if on native page\n"
                "            getTabCreator(currentTab.isIncognito())\n"
                "                    .launchUrl(\"chrome://inspect/#devices\", TabLaunchType.FROM_CHROME_UI);\n"
                "            return true;\n"
                "        }\n"
                "        if (id == R.id.dev_tools\n"
                "                && DevToolsWindowAndroid.isDevToolsAllowedFor(\n"
                "                        this, currentTab.getProfile(), webContents)) {\n"
                "            DevToolsWindowAndroid.openDevTools(webContents);",
                "chrome_activity_devtools_native_page_inspect",
            )
        )
    return results


def patch_inspect_webui_android(chromium_src: Path) -> list[str]:
    """Enable chrome://inspect (#devices, #pages, #extensions, #service-workers) on Android."""
    results = []
    res_inspect_gn = chromium_src / "chrome/browser/resources/inspect/BUILD.gn"
    if res_inspect_gn.exists():
        results.append(
            _patch_text(
                res_inspect_gn,
                "# Kiwi Next: enable inspect resources on Android",
                r"^assert\(!is_android\)",
                "# Kiwi Next: enable inspect resources on Android",
                "resources_inspect_build_gn",
            )
        )

    inspect_js = chromium_src / "chrome/browser/resources/inspect/inspect.js"
    if inspect_js.exists():
        results.append(
            _patch_text(
                inspect_js,
                "device:kiwi-local",
                r"(    } else \{\n      addToOthersList\(data\[i\]\);\n    \}\n  \})",
                r"\1\n"
                "  populateRemoteTargets([{\n"
                "    id: 'device:kiwi-local',\n"
                "    adbModel: 'Kiwi Next (Local Device)',\n"
                "    adbSerial: 'LOCAL',\n"
                "    adbConnected: true,\n"
                "    browsers: [{\n"
                "      id: 'browser:kiwi-next',\n"
                "      source: 'local',\n"
                "      adbBrowserName: 'Kiwi Next',\n"
                "      adbBrowserVersion: (HOST_CHROME_VERSION || [160, 0, 8157, 3]).join('.'),\n"
                "      adbBrowserChromeVersion: (HOST_CHROME_VERSION && HOST_CHROME_VERSION[0]) || 160,\n"
                "      pages: data,\n"
                "    }],\n"
                "  }]);",
                "inspect_js_populate_local_device",
            )
        )

    res_gn = chromium_src / "chrome/browser/resources/BUILD.gn"
    if res_gn.exists():
        results.append(
            _patch_text(
                res_gn,
                "    \"inspect:resources\",  # Kiwi Next",
                r'  public_deps = \[\n    "contextual_tasks:resources",',
                '  public_deps = [\n    "inspect:resources",  # Kiwi Next\n    "contextual_tasks:resources",',
                "resources_build_gn_add_inspect",
            )
        )
        results.append(
            _patch_text(
                res_gn,
                "      # \"inspect:resources\",  # Kiwi Next moved",
                r'      "inspect:resources",',
                '      # "inspect:resources",  # Kiwi Next moved',
                "resources_build_gn_remove_dup_inspect",
            )
        )

    paks_gni = chromium_src / "chrome/chrome_paks.gni"
    if paks_gni.exists():
        results.append(
            _patch_text(
                paks_gni,
                '"$root_gen_dir/chrome/inspect_resources.pak",  # Kiwi Next',
                r'      "\$root_gen_dir/third_party/blink/public/resources/inspector_overlay_resources\.pak",',
                '      "$root_gen_dir/chrome/inspect_resources.pak",  # Kiwi Next\n'
                '      "$root_gen_dir/third_party/blink/public/resources/inspector_overlay_resources.pak",',
                "chrome_paks_add_inspect",
            )
        )
        results.append(
            _patch_text(
                paks_gni,
                '# "$root_gen_dir/chrome/inspect_resources.pak",  # Kiwi Next moved',
                r'        "\$root_gen_dir/chrome/inspect_resources\.pak",',
                '        # "$root_gen_dir/chrome/inspect_resources.pak",  # Kiwi Next moved',
                "chrome_paks_remove_dup_inspect",
            )
        )

    devtools_gn = chromium_src / "chrome/browser/devtools/BUILD.gn"
    if devtools_gn.exists():
        results.append(
            _patch_text(
                devtools_gn,
                '"devtools_targets_ui.cc",  # Kiwi Next',
                r'      "devtools_window_android\.cc",',
                '      "devtools_targets_ui.cc",  # Kiwi Next\n'
                '      "devtools_targets_ui.h",\n'
                '      "serialize_host_descriptions.cc",\n'
                '      "serialize_host_descriptions.h",\n'
                '      "devtools_window_android.cc",',
                "devtools_build_gn_targets_ui",
            )
        )

    targets_ui_cc = chromium_src / "chrome/browser/devtools/devtools_targets_ui.cc"
    if targets_ui_cc.exists():
        results.append(
            _patch_text(
                targets_ui_cc,
                "// Kiwi Next: guard media_router on Android",
                r'#include "components/media_router/browser/presentation/local_presentation_manager\.h"\n'
                r'#include "components/media_router/browser/presentation/local_presentation_manager_factory\.h"',
                "// Kiwi Next: guard media_router on Android\n"
                "#if BUILDFLAG(IS_ANDROID)\n"
                '#include "chrome/browser/ui/android/tab_model/tab_model.h"\n'
                '#include "chrome/browser/ui/android/tab_model/tab_model_list.h"\n'
                "#else\n"
                '#include "components/media_router/browser/presentation/local_presentation_manager.h"\n'
                '#include "components/media_router/browser/presentation/local_presentation_manager_factory.h"\n'
                "#endif",
                "devtools_targets_ui_includes",
            )
        )
        results.append(
            _patch_text(
                targets_ui_cc,
                "// Kiwi Next: LocalTargetsUIHandler Android Open",
                r"  // DevToolsTargetsUIHandler overrides\.\n"
                r"  void ForceUpdate\(\) override;\n\n"
                r"private:\n"
                r" // content::DevToolsAgentHostObserver overrides\.\n"
                r" bool ShouldForceDevToolsAgentHostCreation\(\) override;\n"
                r" void DevToolsAgentHostCreated\(DevToolsAgentHost\* host\) override;\n"
                r" void DevToolsAgentHostDestroyed\(DevToolsAgentHost\* host\) override;\n\n"
                r" void ScheduleUpdate\(\);\n"
                r" void UpdateTargets\(\);\n\n"
                r" bool AllowDevToolsFor\(DevToolsAgentHost\* host\);\n\n"
                r" raw_ptr<Profile> profile_;\n"
                r" raw_ptr<media_router::LocalPresentationManager> local_presentation_manager_;\n"
                r" std::unique_ptr<base::OneShotTimer> timer_;\n"
                r" base::WeakPtrFactory<LocalTargetsUIHandler> weak_factory_\{this\};\n"
                r"\};\n\n"
                r"LocalTargetsUIHandler::LocalTargetsUIHandler\(const Callback& callback,\n"
                r"                                             Profile\* profile\)\n"
                r"    : DevToolsTargetsUIHandler\(kTargetSourceLocal, callback\),\n"
                r"      profile_\(profile\),\n"
                r"      local_presentation_manager_\(\n"
                r"          media_router::LocalPresentationManagerFactory::\n"
                r"              GetOrCreateForBrowserContext\(profile_\)\) \{",
                "  // DevToolsTargetsUIHandler overrides.\n"
                "  void ForceUpdate() override;\n"
                "#if BUILDFLAG(IS_ANDROID)\n"
                "  // Kiwi Next: LocalTargetsUIHandler Android Open\n"
                "  void Open(const std::string& browser_id, const std::string& url) override {\n"
                "    if (!TabModelList::models().empty()) {\n"
                "      TabModelList::models().front()->OpenTab(GURL(url), -1, true);\n"
                "    }\n"
                "  }\n"
                "#endif\n\n"
                "private:\n"
                " // content::DevToolsAgentHostObserver overrides.\n"
                " bool ShouldForceDevToolsAgentHostCreation() override;\n"
                " void DevToolsAgentHostCreated(DevToolsAgentHost* host) override;\n"
                " void DevToolsAgentHostDestroyed(DevToolsAgentHost* host) override;\n\n"
                " void ScheduleUpdate();\n"
                " void UpdateTargets();\n\n"
                " bool AllowDevToolsFor(DevToolsAgentHost* host);\n\n"
                " raw_ptr<Profile> profile_;\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                " raw_ptr<media_router::LocalPresentationManager> local_presentation_manager_;\n"
                "#endif\n"
                " std::unique_ptr<base::OneShotTimer> timer_;\n"
                " base::WeakPtrFactory<LocalTargetsUIHandler> weak_factory_{this};\n"
                "};\n\n"
                "LocalTargetsUIHandler::LocalTargetsUIHandler(const Callback& callback,\n"
                "                                             Profile* profile)\n"
                "    : DevToolsTargetsUIHandler(kTargetSourceLocal, callback),\n"
                "      profile_(profile)\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "      ,\n"
                "      local_presentation_manager_(\n"
                "          media_router::LocalPresentationManagerFactory::\n"
                "              GetOrCreateForBrowserContext(profile_))\n"
                "#endif\n"
                "      {",
                "devtools_targets_ui_local_handler",
            )
        )
        results.append(
            _patch_text(
                targets_ui_cc,
                "// Kiwi Next: guard AllowDevToolsFor and AdbTargetsUIHandler on Android",
                r"bool LocalTargetsUIHandler::AllowDevToolsFor\(DevToolsAgentHost\* host\) \{\n"
                r"  return local_presentation_manager_->IsLocalPresentation\(\n"
                r"             host->GetWebContents\(\)\) \|\|\n"
                r"         \(Profile::FromBrowserContext\(host->GetBrowserContext\(\)\) == profile_ &&\n"
                r"          DevToolsWindow::AllowDevToolsFor\(profile_, host\)\);\n"
                r"\}\n\n"
                r"// AdbTargetsUIHandler --------------------------------------------------------",
                "// Kiwi Next: guard AllowDevToolsFor and AdbTargetsUIHandler on Android\n"
                "bool LocalTargetsUIHandler::AllowDevToolsFor(DevToolsAgentHost* host) {\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "  if (local_presentation_manager_ &&\n"
                "      local_presentation_manager_->IsLocalPresentation(\n"
                "          host->GetWebContents())) {\n"
                "    return true;\n"
                "  }\n"
                "#endif\n"
                "  return Profile::FromBrowserContext(host->GetBrowserContext()) == profile_ &&\n"
                "         DevToolsWindow::AllowDevToolsFor(profile_, host);\n"
                "}\n\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "// AdbTargetsUIHandler --------------------------------------------------------",
                "devtools_targets_ui_allow_and_adb_start",
            )
        )
        results.append(
            _patch_text(
                targets_ui_cc,
                "// Kiwi Next: end AdbTargetsUIHandler guard",
                r"\}\s*// namespace\n\n// DevToolsTargetsUIHandler ---------------------------------------------------",
                "#endif  // !BUILDFLAG(IS_ANDROID)\n"
                "// Kiwi Next: end AdbTargetsUIHandler guard\n"
                "}  // namespace\n\n"
                "// DevToolsTargetsUIHandler ---------------------------------------------------",
                "devtools_targets_ui_adb_end",
            )
        )
        results.append(
            _patch_text(
                targets_ui_cc,
                "// Kiwi Next: guard CreateForAdb and PortForwarding on Android",
                r"// static\n"
                r"std::unique_ptr<DevToolsTargetsUIHandler>\n"
                r"DevToolsTargetsUIHandler::CreateForAdb\(\n"
                r"    DevToolsTargetsUIHandler::Callback callback,\n"
                r"    Profile\* profile\) \{\n"
                r"  return std::unique_ptr<DevToolsTargetsUIHandler>\(\n"
                r"      new AdbTargetsUIHandler\(callback, profile\)\);\n"
                r"\}",
                "// static\n"
                "std::unique_ptr<DevToolsTargetsUIHandler>\n"
                "DevToolsTargetsUIHandler::CreateForAdb(\n"
                "    DevToolsTargetsUIHandler::Callback callback,\n"
                "    Profile* profile) {\n"
                "  // Kiwi Next: guard CreateForAdb and PortForwarding on Android\n"
                "#if BUILDFLAG(IS_ANDROID)\n"
                "  return nullptr;\n"
                "#else\n"
                "  return std::unique_ptr<DevToolsTargetsUIHandler>(\n"
                "      new AdbTargetsUIHandler(callback, profile));\n"
                "#endif\n"
                "}",
                "devtools_targets_ui_create_for_adb",
            )
        )
        results.append(
            _patch_text(
                targets_ui_cc,
                "// Kiwi Next: guard PortForwardingStatusSerializer on Android",
                r"PortForwardingStatusSerializer::PortForwardingStatusSerializer\(\n"
                r"    const Callback& callback, Profile\* profile\)\n"
                r"      : callback_\(callback\),\n"
                r"        profile_\(profile\) \{\n"
                r"  DevToolsAndroidBridge\* android_bridge =\n"
                r"      DevToolsAndroidBridge::Factory::GetForProfile\(profile_\);\n"
                r"  if \(android_bridge\)\n"
                r"    android_bridge->AddPortForwardingListener\(this\);\n"
                r"\}\n\n"
                r"PortForwardingStatusSerializer::~PortForwardingStatusSerializer\(\) \{\n"
                r"  DevToolsAndroidBridge\* android_bridge =\n"
                r"      DevToolsAndroidBridge::Factory::GetForProfile\(profile_\);\n"
                r"  if \(android_bridge\)\n"
                r"    android_bridge->RemovePortForwardingListener\(this\);\n"
                r"\}\n\n"
                r"void PortForwardingStatusSerializer::PortStatusChanged\(\n"
                r"    const ForwardingStatus& status\) \{\n"
                r"  base::DictValue result;\n"
                r"  for \(const auto& status_pair : status\) \{",
                "// Kiwi Next: guard PortForwardingStatusSerializer on Android\n"
                "PortForwardingStatusSerializer::PortForwardingStatusSerializer(\n"
                "    const Callback& callback, Profile* profile)\n"
                "      : callback_(callback),\n"
                "        profile_(profile) {\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "  DevToolsAndroidBridge* android_bridge =\n"
                "      DevToolsAndroidBridge::Factory::GetForProfile(profile_);\n"
                "  if (android_bridge)\n"
                "    android_bridge->AddPortForwardingListener(this);\n"
                "#endif\n"
                "}\n\n"
                "PortForwardingStatusSerializer::~PortForwardingStatusSerializer() {\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "  DevToolsAndroidBridge* android_bridge =\n"
                "      DevToolsAndroidBridge::Factory::GetForProfile(profile_);\n"
                "  if (android_bridge)\n"
                "    android_bridge->RemovePortForwardingListener(this);\n"
                "#endif\n"
                "}\n\n"
                "void PortForwardingStatusSerializer::PortStatusChanged(\n"
                "    const ForwardingStatus& status) {\n"
                "  base::DictValue result;\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "  for (const auto& status_pair : status) {",
                "devtools_targets_ui_port_forwarding",
            )
        )
        results.append(
            _patch_text(
                targets_ui_cc,
                "// Kiwi Next: end PortStatusChanged guard",
                r"    result\.Set\(device_id, std::move\(device_status_dict\)\);\n"
                r"  \}\n"
                r"  callback_\.Run\(base::Value\(std::move\(result\)\)\);",
                "    result.Set(device_id, std::move(device_status_dict));\n"
                "  }\n"
                "#endif\n"
                "  // Kiwi Next: end PortStatusChanged guard\n"
                "  callback_.Run(base::Value(std::move(result)));",
                "devtools_targets_ui_port_status_end",
            )
        )

    webui_inspect_gn = chromium_src / "chrome/browser/ui/webui/inspect/BUILD.gn"
    if webui_inspect_gn.exists():
        results.append(
            _patch_text(
                webui_inspect_gn,
                "# Kiwi Next: enable webui/inspect on Android",
                r'assert\(!is_android\)\n\n'
                r'source_set\("inspect"\) \{\n'
                r'  sources = \[\n'
                r'    "inspect_ui\.cc",\n'
                r'    "inspect_ui\.h",\n'
                r'  \]\n\n'
                r'  deps = \[\n'
                r'    "//base",\n'
                r'    "//chrome/browser:browser_process",\n'
                r'    "//chrome/browser/devtools",\n'
                r'    "//chrome/browser/profiles:profile",\n'
                r'    "//chrome/browser/resources/inspect:resources",\n'
                r'    "//chrome/browser/ui:singleton_tabs",\n'
                r'    "//chrome/browser/ui/webui:favicon_source",\n'
                r'    "//chrome/browser/ui/webui:theme_source",\n'
                r'    "//chrome/common",\n'
                r'    "//components/prefs",\n'
                r'    "//components/ui_devtools",\n'
                r'    "//components/ui_devtools/views",\n'
                r'    "//content/public/browser",\n'
                r'    "//net",\n'
                r'    "//ui/base",\n'
                r'    "//ui/views",\n'
                r'  \]\n'
                r'\}',
                '# Kiwi Next: enable webui/inspect on Android\n'
                'source_set("inspect") {\n'
                '  sources = [\n'
                '    "inspect_ui.cc",\n'
                '    "inspect_ui.h",\n'
                '  ]\n\n'
                '  deps = [\n'
                '    "//base",\n'
                '    "//chrome/browser:browser_process",\n'
                '    "//chrome/browser/devtools",\n'
                '    "//chrome/browser/profiles:profile",\n'
                '    "//chrome/browser/resources/inspect:resources",\n'
                '    "//chrome/browser/ui/webui:favicon_source",\n'
                '    "//chrome/browser/ui/webui:theme_source",\n'
                '    "//chrome/common",\n'
                '    "//components/prefs",\n'
                '    "//content/public/browser",\n'
                '    "//net",\n'
                '    "//ui/base",\n'
                '  ]\n'
                '  if (!is_android) {\n'
                '    deps += [\n'
                '      "//chrome/browser/ui:singleton_tabs",\n'
                '      "//components/ui_devtools",\n'
                '      "//components/ui_devtools/views",\n'
                '      "//ui/views",\n'
                '    ]\n'
                '  }\n'
                '}',
                "webui_inspect_build_gn",
            )
        )

    inspect_ui_cc = chromium_src / "chrome/browser/ui/webui/inspect/inspect_ui.cc"
    if inspect_ui_cc.exists():
        results.append(
            _patch_text(
                inspect_ui_cc,
                "// Kiwi Next: guard desktop includes on Android",
                r'#include "chrome/browser/ui/singleton_tabs\.h"',
                '// Kiwi Next: guard desktop includes on Android\n'
                '#if !BUILDFLAG(IS_ANDROID)\n'
                '#include "chrome/browser/ui/singleton_tabs.h"\n'
                '#endif',
                "inspect_ui_singleton_tabs_include",
            )
        )
        results.append(
            _patch_text(
                inspect_ui_cc,
                "// Kiwi Next: guard ui_devtools and views includes on Android",
                r'#include "components/ui_devtools/devtools_server\.h"\n'
                r'#include "components/ui_devtools/switches\.h"\n'
                r'#include "components/ui_devtools/views/server_holder\.h"',
                '// Kiwi Next: guard ui_devtools and views includes on Android\n'
                '#if !BUILDFLAG(IS_ANDROID)\n'
                '#include "components/ui_devtools/devtools_server.h"\n'
                '#include "components/ui_devtools/switches.h"\n'
                '#include "components/ui_devtools/views/server_holder.h"\n'
                '#endif',
                "inspect_ui_ui_devtools_includes",
            )
        )
        results.append(
            _patch_text(
                inspect_ui_cc,
                "// Kiwi Next: guard views widget and BubbleLocking on Android",
                r'#include "ui/views/widget/widget\.h"\n\n'
                r'using content::DevToolsAgentHost;\n'
                r'using content::WebContents;\n'
                r'using content::WebUIMessageHandler;\n\n'
                r'namespace ui_devtools \{\n\n'
                r'// This class is a friend of views::Widget\.\n'
                r'class BubbleLocking \{\n'
                r' public:\n'
                r'  static void SetEnabled\(bool enabled\) \{\n'
                r'    views::Widget::SetDisableActivationChangeHandling\(\n'
                r'        enabled \? views::Widget::DisableActivationChangeHandlingType::\n'
                r'                      kIgnoreDeactivationOnly\n'
                r'                : views::Widget::DisableActivationChangeHandlingType::kNone\);\n'
                r'  \}\n\n'
                r'  static bool GetEnabled\(\) \{\n'
                r'    return views::Widget::GetDisableActivationChangeHandling\(\) !=\n'
                r'           views::Widget::DisableActivationChangeHandlingType::kNone;\n'
                r'  \}\n\n'
                r' private:\n'
                r'  BubbleLocking\(\) = default;\n'
                r'\};\n\n'
                r'\}  // namespace ui_devtools',
                '// Kiwi Next: guard views widget and BubbleLocking on Android\n'
                '#if !BUILDFLAG(IS_ANDROID)\n'
                '#include "ui/views/widget/widget.h"\n'
                '#endif\n\n'
                'using content::DevToolsAgentHost;\n'
                'using content::WebContents;\n'
                'using content::WebUIMessageHandler;\n\n'
                'namespace ui_devtools {\n'
                'class BubbleLocking {\n'
                ' public:\n'
                '  static void SetEnabled(bool enabled) {\n'
                '#if !BUILDFLAG(IS_ANDROID)\n'
                '    views::Widget::SetDisableActivationChangeHandling(\n'
                '        enabled ? views::Widget::DisableActivationChangeHandlingType::\n'
                '                      kIgnoreDeactivationOnly\n'
                '                : views::Widget::DisableActivationChangeHandlingType::kNone);\n'
                '#endif\n'
                '  }\n'
                '  static bool GetEnabled() {\n'
                '#if !BUILDFLAG(IS_ANDROID)\n'
                '    return views::Widget::GetDisableActivationChangeHandling() !=\n'
                '           views::Widget::DisableActivationChangeHandlingType::kNone;\n'
                '#else\n'
                '    return false;\n'
                '#endif\n'
                '  }\n'
                ' private:\n'
                '  BubbleLocking() = default;\n'
                '};\n'
                '}  // namespace ui_devtools',
                "inspect_ui_bubble_locking",
            )
        )
        results.append(
            _patch_text(
                inspect_ui_cc,
                "// Kiwi Next: guard GetUiDevToolsTargets on Android",
                r"base::ListValue GetUiDevToolsTargets\(\) \{\n"
                r"  base::ListValue targets;\n"
                r"  for \(const auto& client_pair :\n"
                r"       ui_devtools::UiDevToolsServer::GetClientNamesAndUrls\(\)\) \{\n"
                r"    base::DictValue target_data;\n"
                r"    target_data\.Set\(kInspectUiNameField, client_pair\.first\);\n"
                r"    target_data\.Set\(kInspectUiUrlField, client_pair\.second\);\n"
                r"    target_data\.Set\(kInspectUiIsNativeField, true\);\n"
                r"    targets\.Append\(std::move\(target_data\)\);\n"
                r"  \}\n"
                r"  return targets;\n"
                r"\}",
                "// Kiwi Next: guard GetUiDevToolsTargets on Android\n"
                "base::ListValue GetUiDevToolsTargets() {\n"
                "  base::ListValue targets;\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "  for (const auto& client_pair :\n"
                "       ui_devtools::UiDevToolsServer::GetClientNamesAndUrls()) {\n"
                "    base::DictValue target_data;\n"
                "    target_data.Set(kInspectUiNameField, client_pair.first);\n"
                "    target_data.Set(kInspectUiUrlField, client_pair.second);\n"
                "    target_data.Set(kInspectUiIsNativeField, true);\n"
                "    targets.Append(std::move(target_data));\n"
                "  }\n"
                "#endif\n"
                "  return targets;\n"
                "}",
                "inspect_ui_get_targets",
            )
        )
        results.append(
            _patch_text(
                inspect_ui_cc,
                "// Kiwi Next: guard HandleLaunchUIDevToolsCommand on Android",
                r"void InspectMessageHandler::HandleLaunchUIDevToolsCommand\(\n"
                r"    const base::ListValue& args\) \{\n"
                r"  // Start the UI DevTools server if needed and launch the front-end\.",
                "void InspectMessageHandler::HandleLaunchUIDevToolsCommand(\n"
                "    const base::ListValue& args) {\n"
                "  // Kiwi Next: guard HandleLaunchUIDevToolsCommand on Android\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "  // Start the UI DevTools server if needed and launch the front-end.",
                "inspect_ui_launch_ui_devtools_start",
            )
        )
        results.append(
            _patch_text(
                inspect_ui_cc,
                "// Kiwi Next: end HandleLaunchUIDevToolsCommand guard",
                r"  if \(!pairs\.empty\(\)\) \{\n"
                r"    CreateNativeUIInspectionSession\(pairs\[0\]\.second\);\n"
                r"  \}\n"
                r"\}",
                "  if (!pairs.empty()) {\n"
                "    CreateNativeUIInspectionSession(pairs[0].second);\n"
                "  }\n"
                "#endif\n"
                "  // Kiwi Next: end HandleLaunchUIDevToolsCommand guard\n"
                "}",
                "inspect_ui_launch_ui_devtools_end",
            )
        )
        results.append(
            _patch_text(
                inspect_ui_cc,
                "// Kiwi Next: guard InspectDevices and StartListeningNotifications on Android",
                r"void InspectUI::InspectDevices\(BrowserWindowInterface\* browser\) \{\n"
                r"  base::RecordAction\(base::UserMetricsAction\(\"InspectDevices\"\)\);\n"
                r"  ShowSingletonTabOverwritingNTP\(browser, GURL\(chrome::kChromeUIInspectURL\),\n"
                r"                                 NavigateParams::IGNORE_AND_NAVIGATE\);\n"
                r"\}",
                "// Kiwi Next: guard InspectDevices and StartListeningNotifications on Android\n"
                "void InspectUI::InspectDevices(BrowserWindowInterface* browser) {\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "  base::RecordAction(base::UserMetricsAction(\"InspectDevices\"));\n"
                "  ShowSingletonTabOverwritingNTP(browser, GURL(chrome::kChromeUIInspectURL),\n"
                "                                 NavigateParams::IGNORE_AND_NAVIGATE);\n"
                "#endif\n"
                "}",
                "inspect_ui_inspect_devices",
            )
        )
        results.append(
            _patch_text(
                inspect_ui_cc,
                "// Kiwi Next: guard IsUiDevToolsEnabled and null AdbHandler on Android",
                r"  // Show native UI launch button according to the command line or feature flag\.\n"
                r"  if \(ui_devtools::UiDevToolsServer::IsUiDevToolsEnabled\(\n"
                r"          ui_devtools::switches::kEnableUiDevTools\) \|\|\n"
                r"      base::FeatureList::IsEnabled\(features::kUIDebugTools\)\) \{\n"
                r"    ShowNativeUILaunchButton\(/\* enabled = \*/ true\);\n"
                r"  \}\n\n"
                r"  AddTargetUIHandler\(\n"
                r"      DevToolsTargetsUIHandler::CreateForLocal\(callback, profile\)\);\n"
                r"  if \(profile->IsOffTheRecord\(\)\) \{\n"
                r"    ShowIncognitoWarning\(\);\n"
                r"  \} else \{\n"
                r"    AddTargetUIHandler\(\n"
                r"        DevToolsTargetsUIHandler::CreateForAdb\(callback, profile\)\);\n"
                r"  \}",
                "  // Kiwi Next: guard IsUiDevToolsEnabled and null AdbHandler on Android\n"
                "#if !BUILDFLAG(IS_ANDROID)\n"
                "  if (ui_devtools::UiDevToolsServer::IsUiDevToolsEnabled(\n"
                "          ui_devtools::switches::kEnableUiDevTools) ||\n"
                "      base::FeatureList::IsEnabled(features::kUIDebugTools)) {\n"
                "    ShowNativeUILaunchButton(/* enabled = */ true);\n"
                "  }\n"
                "#endif\n\n"
                "  AddTargetUIHandler(\n"
                "      DevToolsTargetsUIHandler::CreateForLocal(callback, profile));\n"
                "  if (profile->IsOffTheRecord()) {\n"
                "    ShowIncognitoWarning();\n"
                "  } else if (auto adb_handler =\n"
                "                 DevToolsTargetsUIHandler::CreateForAdb(callback, profile)) {\n"
                "    AddTargetUIHandler(std::move(adb_handler));\n"
                "  }",
                "inspect_ui_start_listening",
            )
        )

    webui_gn = chromium_src / "chrome/browser/ui/webui/BUILD.gn"
    if webui_gn.exists():
        results.append(
            _patch_text(
                webui_gn,
                '"//chrome/browser/ui/webui/inspect",  # Kiwi Next',
                r'  if \(!is_android \|\| is_desktop_android\) \{\n'
                r'    deps \+= \[ "//chrome/browser/ui/webui/ai_overlay_dialog" \]\n'
                r'  \}',
                '  if (!is_android || is_desktop_android) {\n'
                '    deps += [\n'
                '      "//chrome/browser/ui/webui/ai_overlay_dialog",\n'
                '      "//chrome/browser/ui/webui/inspect",  # Kiwi Next\n'
                '    ]\n'
                '  }',
                "webui_build_gn_add_inspect",
            )
        )

    webui_configs_cc = chromium_src / "chrome/browser/ui/webui/chrome_web_ui_configs.cc"
    if webui_configs_cc.exists():
        results.append(
            _patch_text(
                webui_configs_cc,
                '#include "chrome/browser/ui/webui/inspect/inspect_ui.h"  // Kiwi Next',
                r'#include "chrome/browser/ui/webui/private_ai_internals/private_ai_internals_ui\.h"',
                '#include "chrome/browser/ui/webui/private_ai_internals/private_ai_internals_ui.h"\n'
                '#include "chrome/browser/ui/webui/inspect/inspect_ui.h"  // Kiwi Next',
                "chrome_web_ui_configs_include_inspect",
            )
        )
        results.append(
            _patch_text(
                webui_configs_cc,
                "map.AddWebUIConfig(std::make_unique<InspectUIConfig>());  // Kiwi Next",
                r'  map\.AddWebUIConfig\(std::make_unique<WebApksUIConfig>\(\)\);',
                '  map.AddWebUIConfig(std::make_unique<WebApksUIConfig>());\n'
                '  map.AddWebUIConfig(std::make_unique<InspectUIConfig>());  // Kiwi Next',
                "chrome_web_ui_configs_register_inspect",
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
                    fg.unlink()
                if bg.exists():
                    shutil.copy2(bg, mipmap_dir / "layered_app_icon_background.png")
                    bg.unlink()
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
    results.extend(patch_devtools_open_as_tab(chromium_src))
    results.extend(patch_inspect_webui_android(chromium_src))
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
