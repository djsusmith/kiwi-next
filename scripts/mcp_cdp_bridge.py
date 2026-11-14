"""Shizuku (rish) CDP-to-MCP socket discovery and TCP forwarder for Kiwi/Chrome Dev."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys

SOCKET_PATTERN = re.compile(r"@(\S*devtools_remote\S*)")


def parse_devtools_sockets(proc_net_unix: str) -> list[str]:
    """Extract unique abstract DevTools Unix socket names from /proc/net/unix."""
    seen: list[str] = []
    for line in proc_net_unix.splitlines():
        match = SOCKET_PATTERN.search(line)
        if match:
            name = match.group(1)
            if name not in seen:
                seen.append(name)
    return seen


def list_active_sockets() -> list[str]:
    """Query /proc/net/unix via Shizuku rish for active browser DevTools sockets."""
    if not shutil.which("rish"):
        raise RuntimeError("rish binary not found in PATH; ensure Shizuku is configured.")
    res = subprocess.run(
        ["rish", "-c", "cat /proc/net/unix"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(f"rish failed: {res.stderr.strip()}")
    return parse_devtools_sockets(res.stdout)


def forward_socket(socket_name: str, port: int) -> int:
    """Forward 127.0.0.1:<port> to localabstract:<socket_name> via socat.

    Note: On Android 17+, SELinux (u:r:shell:s0) may deny connecting to
    @*_devtools_remote; in that case, use --local-chromium to launch
    agy-chromium-daemon on 127.0.0.1:<port> or use kiwi_mcp_bridge (ws://127.0.0.1:9223).
    """
    if not shutil.which("socat"):
        raise RuntimeError("socat is required for forwarding; install via: pkg install socat")
    cmd = [
        "socat",
        f"TCP-LISTEN:{port},bind=127.0.0.1,reuseaddr,fork",
        f"ABSTRACT-CONNECT:{socket_name}",
    ]
    print(f"Forwarding http://127.0.0.1:{port} -> @{socket_name} (Ctrl+C to stop)")
    return subprocess.call(cmd)


def launch_local_chromium_daemon() -> int:
    """Start agy-chromium-daemon (native ARM64 Chromium on 127.0.0.1:9222)."""
    daemon = shutil.which("agy-chromium-daemon")
    if not daemon:
        raise RuntimeError("agy-chromium-daemon not found in PATH.")
    return subprocess.call([daemon])


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiwi/Chrome Dev CDP-to-MCP bridge via Shizuku.")
    parser.add_argument("--list-sockets", action="store_true", help="List active DevTools sockets.")
    parser.add_argument("--socket", help="Specific abstract socket name to forward.")
    parser.add_argument("--port", type=int, default=9222, help="Local TCP port (default: 9222).")
    parser.add_argument(
        "--local-chromium",
        action="store_true",
        help="Launch agy-chromium-daemon on 127.0.0.1:9222 (bypasses Android 17 SELinux abstract socket restriction).",
    )
    args = parser.parse_args()

    if args.local_chromium:
        try:
            return launch_local_chromium_daemon()
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    try:
        sockets = list_active_sockets()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.list_sockets:
        if not sockets:
            print("No active *_devtools_remote sockets found. Open Kiwi or Chrome Dev first.")
        else:
            for s in sockets:
                print(s)
        return 0

    target = args.socket or (sockets[0] if sockets else None)
    if not target:
        print("Error: No active *_devtools_remote socket found.", file=sys.stderr)
        return 1

    return forward_socket(target, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
