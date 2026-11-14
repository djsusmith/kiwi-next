#!/usr/bin/env bash
set -euo pipefail

UNINSTALL_PREV=false
if [ "${1:-}" = "--uninstall-previous" ]; then
  UNINSTALL_PREV=true
  shift
fi

if [ "$#" -lt 1 ]; then
  echo "Usage: bash scripts/deploy_shizuku.sh [--uninstall-previous] <apk_path> [package_name]" >&2
  exit 1
fi

APK_PATH="$1"
PKG_NAME="${2:-com.kiwibrowser.browser.dev}"

if [ ! -f "$APK_PATH" ]; then
  echo "Error: APK not found at $APK_PATH" >&2
  exit 1
fi

if [ "$UNINSTALL_PREV" = true ]; then
  echo "Uninstalling previous $PKG_NAME via Shizuku (rish)..."
  rish -c "pm uninstall \"$PKG_NAME\"" || true
fi

echo "Installing signed APK $APK_PATH via Shizuku (rish)..."
rish -c "pm install -r \"$APK_PATH\""

echo "Launching $PKG_NAME..."
rish -c "monkey -p \"$PKG_NAME\" -c android.intent.category.LAUNCHER 1"

echo "Installed package version:"
rish -c "dumpsys package \"$PKG_NAME\" | grep -E 'versionName|versionCode'"
