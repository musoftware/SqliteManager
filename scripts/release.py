"""
scripts/release.py — Release packaging and versioning helper.

Usage:
    python scripts/release.py --bump patch      # 1.0.0 -> 1.0.1
    python scripts/release.py --bump minor      # 1.0.0 -> 1.1.0
    python scripts/release.py --bump major      # 1.0.0 -> 2.0.0
    python scripts/release.py --tag             # create git tag
    python scripts/release.py --changelog       # print CHANGELOG since last tag
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERSION_FILE = ROOT / "app" / "version.py"


def read_version() -> tuple[int, int, int]:
    content = VERSION_FILE.read_text()
    m = re.search(r"VERSION_MAJOR\s*=\s*(\d+)", content)
    mi = re.search(r"VERSION_MINOR\s*=\s*(\d+)", content)
    p = re.search(r"VERSION_PATCH\s*=\s*(\d+)", content)
    return int(m.group(1)), int(mi.group(1)), int(p.group(1))


def write_version(major: int, minor: int, patch: int) -> None:
    content = VERSION_FILE.read_text()
    content = re.sub(r"VERSION_MAJOR\s*=\s*\d+", f"VERSION_MAJOR = {major}", content)
    content = re.sub(r"VERSION_MINOR\s*=\s*\d+", f"VERSION_MINOR = {minor}", content)
    content = re.sub(r"VERSION_PATCH\s*=\s*\d+", f"VERSION_PATCH = {patch}", content)
    VERSION_FILE.write_text(content)
    print(f"  Version updated: {major}.{minor}.{patch}")


def bump_version(part: str) -> tuple[int, int, int]:
    major, minor, patch = read_version()
    if part == "major":
        major += 1; minor = 0; patch = 0
    elif part == "minor":
        minor += 1; patch = 0
    elif part == "patch":
        patch += 1
    else:
        print(f"Unknown bump target: {part}")
        sys.exit(1)
    write_version(major, minor, patch)
    return major, minor, patch


def git_tag(version: str) -> None:
    tag = f"v{version}"
    try:
        subprocess.run(["git", "tag", "-a", tag, "-m", f"Release {tag}"], cwd=ROOT, check=True)
        print(f"  Git tag created: {tag}")
        print(f"  Push with: git push origin {tag}")
    except subprocess.CalledProcessError as e:
        print(f"  Git tag failed: {e}")


def git_changelog() -> None:
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--no-merges", "HEAD...$(git describe --tags --abbrev=0 HEAD^)"],
            cwd=ROOT, capture_output=True, text=True
        )
        if result.stdout:
            print("Changes since last tag:")
            print(result.stdout)
        else:
            print("No changes found or no previous tags.")
    except Exception as e:
        print(f"Could not get changelog: {e}")


def update_installer_iss(version: str) -> None:
    """Update version number in installer.iss"""
    iss = ROOT / "installer" / "installer.iss"
    if not iss.exists():
        return
    content = iss.read_text()
    content = re.sub(r'AppVersion=[\d.]+', f'AppVersion={version}', content)
    content = re.sub(r'OutputBaseFilename=.*', f'OutputBaseFilename=SQLiteManagerSetup_{version}', content)
    iss.write_text(content)
    print(f"  installer.iss updated to v{version}")


def update_version_info_txt(major: int, minor: int, patch: int) -> None:
    """Update installer/version_info.txt"""
    vi = ROOT / "installer" / "version_info.txt"
    if not vi.exists():
        return
    content = vi.read_text()
    vt = f"({major}, {minor}, {patch}, 0)"
    vs = f"{major}.{minor}.{patch}.0"
    content = re.sub(r'\(\d+, \d+, \d+, \d+\)', vt, content)
    content = re.sub(r'\d+\.\d+\.\d+\.\d+', vs, content)
    vi.write_text(content)
    print(f"  version_info.txt updated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite Manager Release Helper")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], help="Bump version")
    parser.add_argument("--tag", action="store_true", help="Create git tag for current version")
    parser.add_argument("--changelog", action="store_true", help="Show changelog since last tag")
    args = parser.parse_args()

    if args.bump:
        major, minor, patch = bump_version(args.bump)
        ver = f"{major}.{minor}.{patch}"
        update_installer_iss(ver)
        update_version_info_txt(major, minor, patch)
        print(f"\nVersion bumped to {ver}")
        print(f"Next: git commit -am 'bump version to {ver}' && python scripts/release.py --tag")

    elif args.tag:
        major, minor, patch = read_version()
        ver = f"{major}.{minor}.{patch}"
        git_tag(ver)

    elif args.changelog:
        git_changelog()

    else:
        major, minor, patch = read_version()
        print(f"Current version: {major}.{minor}.{patch}")
        parser.print_help()
