"""Audit Kiwi Browser's Chromium overlay files against the target Chromium version."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

OVERLAY_DIRS = (
    "base",
    "chrome",
    "components",
    "content",
    "extensions",
    "net",
    "remoting",
    "services",
    "third_party",
    "ui",
)


def parse_version_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE pairs from a Kiwi/Chromium version file, ignoring comments."""
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def audit_overlay(repo_root: Path) -> dict:
    """Inventory Kiwi overlay directories and file counts for Chromium rebasing."""
    top_level_dirs: dict[str, int] = {}
    total_files = 0
    for dirname in OVERLAY_DIRS:
        target = repo_root / dirname
        if not target.is_dir():
            continue
        count = sum(1 for p in target.rglob("*") if p.is_file())
        top_level_dirs[dirname] = count
        total_files += count

    chromium_ver = parse_version_file(repo_root / "CHROMIUM_VERSION")
    version_str = ".".join(
        chromium_ver.get(k, "0")
        for k in ("CHROMIUM_MAJOR", "CHROMIUM_MINOR", "CHROMIUM_BUILD", "CHROMIUM_PATCH")
    )
    return {
        "target_chromium_version": version_str,
        "top_level_dirs": top_level_dirs,
        "total_files": total_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Kiwi Chromium overlay.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to the kiwi-src-next worktree root.",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON report.")
    args = parser.parse_args()
    report = audit_overlay(args.repo_root)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Target Chromium: {report['target_chromium_version']}")
        print(f"Total overlay files: {report['total_files']}")
        for d, count in sorted(report["top_level_dirs"].items()):
            print(f"  {d}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
