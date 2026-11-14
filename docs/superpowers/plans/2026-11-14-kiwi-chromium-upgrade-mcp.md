# Kiwi Browser Chromium Upgrade & MCP Tools Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `kiwibrowser/src.next` to target Chromium `159.0.8144.0`, replace the dead `longbuild.find.kiwi` CI pipeline with a real `depot_tools` Android ARM64 build workflow, add a built-in MCP Bridge extension, and provide Shizuku (`rish`) on-device deployment and CDP-to-MCP socket forwarding scripts.

**Architecture:** Because Chromium Android C++ compilation requires an `x86_64` Linux host (≥150 GB disk, ≥32–64 GB RAM), the repository's GitHub Actions workflow handles `depot_tools` checkout, overlay application, and `autoninja` APK compilation on a self-hosted/large `x86_64` runner. On the Android device (`SM-S938B`), Shizuku (`rish`) handles APK installation (`pm install -r`) and forwards the browser's `localabstract:*_devtools_remote` socket to `127.0.0.1:9222` for AGY's `chrome-devtools` MCP server, complemented by a Manifest V3 `kiwi_mcp_bridge` extension.

**Tech Stack:** Python 3.14 (`unittest`, `yaml`/`json`), Bash, Shizuku (`rish`), Chromium `depot_tools` / GN / Ninja, Chrome Extensions Manifest V3 (JavaScript), GitHub Actions YAML.

**Spec:** `/data/user/0/com.agy/files/.gemini/antigravity-app/brain/f737305a-7de3-4a82-b575-4c617ea38c39/kiwi-chromium-mcp-design.md`

## Global Constraints
- Target Chromium version: `159.0.8144.0` (matching `com.chrome.dev` on-device).
- Target Android ABI: `arm64` (`target_os = "android"`, `target_cpu = "arm64"`, `enable_extensions = true`).
- Never invoke `bwrap` or run `depot_tools` compilation natively on ARM64 Android.
- On Android shared storage or noexec paths, invoke scripts with explicit interpreters (`python3`, `bash`).
- Shizuku elevated commands must use `rish -c "<command>"`.

## Review Focus
- `CHROMIUM_VERSION` / `KIWI_VERSION` parsing fails if comments or blank lines are present -> tested in Task 1.
- Missing or malformed `.build/chromium_159/args.gn` or `longbuild.find.kiwi` still referenced in `build_apk.yml` -> tested in Task 2.
- `kiwi_mcp_bridge` manifest missing required MV3 fields (`manifest_version: 3`, `permissions`, `background.service_worker`) -> tested in Task 3.
- `mcp_cdp_bridge.py` fails gracefully when no browser DevTools socket is open or `rish` is unavailable -> tested in Task 4.
- `deploy_shizuku.sh` validates APK path argument before calling `rish` -> tested in Task 4.

---

### Task 1: Target Version Bump, `.gitignore` Update & Overlay Audit Tool

**Files:**
- Modify: `.gitignore`
- Modify: `CHROMIUM_VERSION`
- Modify: `KIWI_VERSION`
- Create: `scripts/audit_chromium_overlay.py`
- Test: `tests/test_audit_chromium_overlay.py`

**Interfaces:**
- Produces: `parse_version_file(path: Path) -> dict[str, str]`, `audit_overlay(repo_root: Path) -> dict` in `scripts/audit_chromium_overlay.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_chromium_overlay.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_audit_chromium_overlay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.audit_chromium_overlay'`.

- [ ] **Step 3: Update `.gitignore`, `CHROMIUM_VERSION`, `KIWI_VERSION`, and implement `scripts/audit_chromium_overlay.py`**

- Add `.worktrees/` to `.gitignore`.
- Set `CHROMIUM_VERSION` to `159.0.8144.0` and `KIWI_VERSION` to `159.0.8144.0`.
- Implement `parse_version_file(path: Path) -> dict[str, str]` (ignoring `#` comments and blank lines) and `audit_overlay(repo_root: Path) -> dict` (scanning Chromium overlay directories: `base`, `chrome`, `components`, `content`, `extensions`, `net`, `remoting`, `services`, `third_party`, `ui`) in `scripts/audit_chromium_overlay.py` with a CLI entrypoint (`--json`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_audit_chromium_overlay.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add .gitignore CHROMIUM_VERSION KIWI_VERSION scripts/audit_chromium_overlay.py tests/test_audit_chromium_overlay.py
git commit -m "feat: bump target Chromium version to 159.0.8144.0 and add overlay audit tool"
```

---

### Task 2: Self-Hosted / Cloud Chromium Android ARM64 CI Pipeline & GN Config

**Files:**
- Create: `.build/chromium_159/args.gn`
- Modify: `.github/workflows/build_apk.yml`
- Test: `tests/test_workflow_config.py`

**Interfaces:**
- Consumes: `CHROMIUM_VERSION` (`CHROMIUM_MAJOR`, `CHROMIUM_MINOR`, `CHROMIUM_BUILD`, `CHROMIUM_PATCH`).
- Produces: `.build/chromium_159/args.gn` and `.github/workflows/build_apk.yml` using `depot_tools` + `autoninja chrome_public_apk`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_workflow_config.py`:
```python
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestWorkflowConfig(unittest.TestCase):
    def test_build_apk_workflow_no_dead_server(self):
        content = (REPO_ROOT / ".github/workflows/build_apk.yml").read_text()
        self.assertNotIn("longbuild.find.kiwi", content)
        self.assertNotIn("build.find.kiwi", content)
        self.assertIn("autoninja", content)
        self.assertIn("chrome_public_apk", content)
        self.assertIn("CHROMIUM_VERSION", content)

    def test_chromium_159_args_gn(self):
        gn = (REPO_ROOT / ".build/chromium_159/args.gn").read_text()
        self.assertIn('target_os = "android"', gn)
        self.assertIn('target_cpu = "arm64"', gn)
        self.assertIn("enable_extensions = true", gn)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_workflow_config.py -v`
Expected: FAIL (`longbuild.find.kiwi` still present and `.build/chromium_159/args.gn` missing).

- [ ] **Step 3: Create `.build/chromium_159/args.gn` and update `.github/workflows/build_apk.yml`**

- Create `.build/chromium_159/args.gn` based on `.build/production_build_reference/args.gn` updated for Chromium 159 (`target_os = "android"`, `target_cpu = "arm64"`, `enable_extensions = true`, `proprietary_codecs = true`, `ffmpeg_branding = "Chrome"`, `treat_warnings_as_errors = false`, `disable_android_lint = true`).
- Rewrite `.github/workflows/build_apk.yml` to run on `self-hosted` (or configurable `runs-on` input via `workflow_dispatch`, defaulting to `[self-hosted, linux, x64]`), read `CHROMIUM_VERSION`, sync Chromium at that tag via `depot_tools`, overlay Kiwi's modified directories + `extensions/kiwi_mcp_bridge`, run `gn gen out/KiwiArm64`, build `autoninja -C out/KiwiArm64 chrome_public_apk`, and upload the APK artifact.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_workflow_config.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add .build/chromium_159/args.gn .github/workflows/build_apk.yml tests/test_workflow_config.py
git commit -m "ci: replace dead longbuild.find.kiwi with depot_tools Chromium 159 ARM64 workflow"
```

---

### Task 3: Built-in MCP Bridge Chrome Extension (`extensions/kiwi_mcp_bridge/`)

**Files:**
- Create: `extensions/kiwi_mcp_bridge/manifest.json`
- Create: `extensions/kiwi_mcp_bridge/background.js`
- Create: `extensions/kiwi_mcp_bridge/popup.html`
- Create: `extensions/kiwi_mcp_bridge/popup.js`
- Test: `tests/test_mcp_bridge_manifest.py`

**Interfaces:**
- Produces: MV3 extension exposing `kiwi_mcp_list_tabs`, `kiwi_mcp_navigate`, `kiwi_mcp_eval_js`, `kiwi_mcp_capture_screenshot` over WebSocket (`ws://127.0.0.1:9223`) and `chrome.runtime.onMessage`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_bridge_manifest.py`:
```python
import json
import unittest
from pathlib import Path

EXT_DIR = Path(__file__).resolve().parent.parent / "extensions/kiwi_mcp_bridge"


class TestMcpBridgeManifest(unittest.TestCase):
    def test_manifest_mv3_valid(self):
        manifest = json.loads((EXT_DIR / "manifest.json").read_text())
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_mcp_bridge_manifest.py -v`
Expected: FAIL (`FileNotFoundError` on `manifest.json`).

- [ ] **Step 3: Implement `extensions/kiwi_mcp_bridge/`**

- `manifest.json`: MV3 manifest with `tabs`, `scripting`, `activeTab`, `storage`, `host_permissions: ["<all_urls>"]`, `background.service_worker: "background.js"`, and `action.default_popup: "popup.html"`.
- `background.js`: Connects to configurable local MCP WebSocket bridge (`ws://127.0.0.1:9223` by default), handles JSON-RPC tool calls (`list_tabs`, `navigate`, `eval_js`, `capture_screenshot`), and returns structured results.
- `popup.html` & `popup.js`: Minimal status UI showing bridge connection state and allowing endpoint configuration.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_mcp_bridge_manifest.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add extensions/kiwi_mcp_bridge/ tests/test_mcp_bridge_manifest.py
git commit -m "feat: add MV3 kiwi_mcp_bridge extension for MCP tool integration"
```

---

### Task 4: On-Device Shizuku (`rish`) CDP-to-MCP Bridge & APK Deploy Script

**Files:**
- Create: `scripts/mcp_cdp_bridge.py`
- Create: `scripts/deploy_shizuku.sh`
- Test: `tests/test_mcp_cdp_bridge.py`

**Interfaces:**
- Produces: `parse_devtools_sockets(proc_net_unix: str) -> list[str]` and CLI `scripts/mcp_cdp_bridge.py` (`--port 9222`, `--list-sockets`, `--socket <name>`); `scripts/deploy_shizuku.sh <apk_path> [package_name]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_cdp_bridge.py`:
```python
import subprocess
import unittest
from pathlib import Path
from scripts.mcp_cdp_bridge import parse_devtools_sockets

REPO_ROOT = Path(__file__).resolve().parent.parent

SAMPLE_PROC_NET_UNIX = """Num       RefCount Protocol Flags    Type St Inode Path
00000000: 00000002 00000000 00010000 0001 01 12345 @chrome_devtools_remote
00000000: 00000002 00000000 00010000 0001 01 12346 @kiwi_devtools_remote_999
00000000: 00000002 00000000 00010000 0001 01 12347 /dev/socket/zygote
"""


class TestMcpCdpBridge(unittest.TestCase):
    def test_parse_devtools_sockets(self):
        sockets = parse_devtools_sockets(SAMPLE_PROC_NET_UNIX)
        self.assertEqual(sockets, ["chrome_devtools_remote", "kiwi_devtools_remote_999"])

    def test_deploy_shizuku_requires_apk_arg(self):
        res = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts/deploy_shizuku.sh")],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Usage:", res.stderr + res.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_mcp_cdp_bridge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.mcp_cdp_bridge'`.

- [ ] **Step 3: Implement `scripts/mcp_cdp_bridge.py` and `scripts/deploy_shizuku.sh`**

- `scripts/mcp_cdp_bridge.py`:
  - `parse_devtools_sockets(proc_net_unix: str) -> list[str]` extracts `@*_devtools_remote*` abstract Unix socket names.
  - Queries `/proc/net/unix` via `rish -c "cat /proc/net/unix"` when `--list-sockets` or forwarding is invoked, and forwards `127.0.0.1:<port>` to the chosen `localabstract:<socket>` via `rish` + `socat`/Python asyncio stream bridge so AGY's `chrome-devtools` MCP server can connect on `http://127.0.0.1:9222`.
- `scripts/deploy_shizuku.sh`:
  - Validates `<apk_path>` exists (prints `Usage:` to stderr and exits 1 if missing).
  - Runs `rish -c "pm install -r <apk_path>"`, launches the browser activity, and prints `dumpsys package <pkg> | grep versionName`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_mcp_cdp_bridge.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/mcp_cdp_bridge.py scripts/deploy_shizuku.sh tests/test_mcp_cdp_bridge.py
git commit -m "feat: add Shizuku rish CDP-to-MCP bridge and APK deploy script"
```
