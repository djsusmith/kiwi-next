# Kiwi Next Authentic Features Porting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port Kiwi's authentic features (extensions system, developer tools, desktop UI/bottom toolbar, AMOLED night mode, Kiwi branding) into Chromium 160 with integrated MCP AI agent tools.

**Architecture:** Utilize modern Chromium 160's native desktop extensions subsystem (`is_desktop_android = true`, enabling `enable_desktop_android_extensions`), overlay Kiwi's authentic 3-dots App Menu (`chrome/android/java/res/menu/main_menu.xml`), restore Kiwi's drawables and string resources, connect the extensions management UI to `chrome://extensions`, and maintain the Model Context Protocol (MCP) WebSocket server on `ws://127.0.0.1:9223`.

**Tech Stack:** Chromium 160 Dev (`160.0.8157.3`), Android 17 (API 37), GN/Ninja build system, Java / Android SDK, Google `depot_tools`, Manifest V3 Extensions, WebSockets / MCP.

**Spec:** Porting Kiwi Browser features from `kiwibrowser/src.next` (branch `kiwi`) to modern Chromium 160 (`djsusmith/kiwi-next`).

---

## Global Constraints

- **Chromium Target Version:** `160.0.8157.3`
- **Architecture:** ARM64 (`aarch64`, Snapdragon 8 Elite / Android 17 API 37)
- **Host Build Platform:** Ubuntu 24.04 x86_64 (`ec2-13-61-33-233.eu-north-1.compute.amazonaws.com`)
- **Key GN Arguments:**
  - `target_os = "android"`
  - `target_cpu = "arm64"`
  - `is_desktop_android = true` (enables `enable_desktop_android_extensions = true`)
  - `is_official_build = false`
  - `is_debug = false`
  - `symbol_level = 0`
- **Credits:** Ahnaf Hasan Susmith with Antigravity (`susdj.96@gmail.com`)

---

## Task Decomposition

### Task 1: Enable Desktop Android Extensions in GN Args
- [ ] Update `.build/chromium_159/args.gn` with `is_desktop_android = true`.
- [ ] Verify `gn gen` generates build graph without errors on EC2 runner.
- [ ] Verify `enable_desktop_android_extensions == true` via `gn args --list`.

### Task 2: Port Kiwi Authentic App Menu & Resources
- [ ] Extract Kiwi's authentic `chrome/android/java/res/menu/main_menu.xml` (including Extensions, Developer tools, Night mode, and Ad block items).
- [ ] Copy Kiwi drawables (`ic_extensions.xml`, `ic_devtools.xml`, `ic_desktop_mode.xml`, `ic_zoom.xml`, `ic_translate_r.xml`).
- [ ] Overlay Kiwi localized strings (`main_menu_extensions`, `main_menu_developer_tools`, `main_menu_turn_on_night_mode`, etc.).
- [ ] Add menu click handlers in `AppMenuPropertiesDelegateImpl.java` or `ChromeTabbedActivity.java` to launch `chrome://extensions` and Developer Tools.

### Task 3: Port Kiwi Night Mode (AMOLED Black Contrast)
- [ ] Wire night mode toggle in App Menu to WebContents dark mode settings.
- [ ] Integrate AMOLED 100% black background preference for Samsung Galaxy AMOLED screens.

### Task 4: Integrate Kiwi MCP Bridge & Sideloading
- [ ] Bundle `extensions/kiwi_mcp_bridge/` into Chromium's default unpacked extension load path.
- [ ] Test WebSocket bridge communication on `ws://127.0.0.1:9223`.

### Task 5: Kiwi Next Branding & Packaging
- [ ] Update application title to "Kiwi Next" across strings and AndroidManifest.
- [ ] Replace Chromium default icon with `kiwi_logo_circle.svg`.

### Task 6: Autonomous Compilation & Deployment on Device
- [ ] Run ninja compilation (`autoninja -C out/KiwiArm64 chrome_public_apk`).
- [ ] Deploy compiled APK via Shizuku (`rish -c "pm install -r -d /data/local/tmp/..."`).
- [ ] Verify authentic Kiwi menu, extensions drawer, and MCP bridge on physical device.
- [ ] Upload final verified binary to GitHub Releases.
