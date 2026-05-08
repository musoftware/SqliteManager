"""
scripts/clean.py — Clean all build artifacts.

Usage:
    python scripts/clean.py           # clean build/dist
    python scripts/clean.py --full    # also clear __pycache__, .pyc
    python scripts/clean.py --releases # also remove releases/
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def clean(full: bool = False, releases: bool = False) -> None:
    removed = []

    dirs_to_clean = [ROOT / "build", ROOT / "dist"]
    if releases:
        dirs_to_clean.append(ROOT / "releases")

    for d in dirs_to_clean:
        if d.exists():
            shutil.rmtree(d)
            removed.append(str(d))

    if full:
        for pycache in ROOT.rglob("__pycache__"):
            shutil.rmtree(pycache)
        for pyc in ROOT.rglob("*.pyc"):
            pyc.unlink()
        for spec_bak in ROOT.glob("*.spec~"):
            spec_bak.unlink()
        removed.append("__pycache__ + .pyc files")

    if removed:
        print("Cleaned:")
        for r in removed:
            print(f"  {r}")
    else:
        print("Nothing to clean.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full",     action="store_true")
    parser.add_argument("--releases", action="store_true")
    args = parser.parse_args()
    clean(full=args.full, releases=args.releases)
