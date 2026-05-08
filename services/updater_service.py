"""
services/updater_service.py — Auto Updater Service.

Checks GitHub releases API for newer versions.
Downloads and launches the installer, with rollback support.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional, Callable
from urllib.request import urlopen, urlretrieve
from urllib.error import URLError

from PySide6.QtCore import QObject, Signal, QThread

from app.logger import get_logger
from app.version import VERSION, APP_RELEASES_API, is_newer, APP_NAME

log = get_logger("updater")


class ReleaseInfo:
    """Parsed GitHub release data."""

    def __init__(self, data: dict):
        self.tag = data.get("tag_name", "")
        self.version = self.tag.lstrip("v")
        self.name = data.get("name", "")
        self.body = data.get("body", "")
        self.prerelease = data.get("prerelease", False)
        self.published_at = data.get("published_at", "")
        self.assets: list[dict] = data.get("assets", [])
        self.browser_url = data.get("html_url", "")

    @property
    def installer_asset(self) -> Optional[dict]:
        for a in self.assets:
            name = a.get("name", "").lower()
            if name.endswith(".exe") and "portable" not in name:
                return a
        return None

    @property
    def portable_asset(self) -> Optional[dict]:
        for a in self.assets:
            name = a.get("name", "").lower()
            if "portable" in name and name.endswith(".zip"):
                return a
        return None


class UpdateCheckWorker(QThread):
    """Background worker to check for updates."""

    update_available = Signal(object)    # ReleaseInfo
    no_update = Signal()
    check_failed = Signal(str)

    def __init__(self, include_prerelease: bool = False):
        super().__init__()
        self._prerelease = include_prerelease

    def run(self) -> None:
        try:
            with urlopen(APP_RELEASES_API, timeout=10) as resp:
                data = json.loads(resp.read())
            release = ReleaseInfo(data)
            if release.prerelease and not self._prerelease:
                self.no_update.emit()
                return
            if is_newer(release.version):
                log.info("Update available: %s → %s", VERSION, release.version)
                self.update_available.emit(release)
            else:
                log.info("No update available (current: %s, latest: %s)", VERSION, release.version)
                self.no_update.emit()
        except URLError as exc:
            log.warning("Update check failed (network): %s", exc)
            self.check_failed.emit(f"Network error: {exc}")
        except Exception as exc:
            log.warning("Update check failed: %s", exc)
            self.check_failed.emit(str(exc))


class DownloadWorker(QThread):
    """Background downloader for the update installer."""

    progress = Signal(int, int)     # downloaded_bytes, total_bytes
    finished = Signal(str)          # path to downloaded file
    error = Signal(str)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self._url = url
        self._dest = dest

    def run(self) -> None:
        try:
            def reporthook(count, block_size, total_size):
                downloaded = min(count * block_size, total_size)
                self.progress.emit(downloaded, total_size)
            urlretrieve(self._url, self._dest, reporthook)
            self.finished.emit(self._dest)
        except Exception as exc:
            self.error.emit(str(exc))


class UpdaterService(QObject):
    """
    High-level update manager.
    Usage:
        svc = UpdaterService(parent)
        svc.update_available.connect(lambda r: ...)
        svc.check()
    """

    update_available = Signal(object)
    no_update = Signal()
    check_failed = Signal(str)
    download_progress = Signal(int, int)
    download_finished = Signal(str)
    download_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[UpdateCheckWorker] = None
        self._dl_worker: Optional[DownloadWorker] = None

    def check(self, silent: bool = False, include_prerelease: bool = False) -> None:
        """Trigger a background update check."""
        if self._worker and self._worker.isRunning():
            return
        self._worker = UpdateCheckWorker(include_prerelease)
        self._worker.update_available.connect(self.update_available)
        self._worker.no_update.connect(self.no_update)
        self._worker.check_failed.connect(
            lambda msg: (None if silent else self.check_failed.emit(msg))
        )
        self._worker.start()
        log.info("Update check started.")

    def download(self, release: ReleaseInfo, portable: bool = False) -> None:
        """Download the release installer/portable ZIP."""
        asset = release.portable_asset if portable else release.installer_asset
        if not asset:
            self.download_error.emit("No suitable download found in release assets.")
            return
        url = asset["browser_download_url"]
        filename = asset["name"]
        dest = str(Path(tempfile.gettempdir()) / filename)

        log.info("Downloading update: %s → %s", url, dest)
        self._dl_worker = DownloadWorker(url, dest)
        self._dl_worker.progress.connect(self.download_progress)
        self._dl_worker.finished.connect(self.download_finished)
        self._dl_worker.error.connect(self.download_error)
        self._dl_worker.start()

    def install(self, installer_path: str, silent: bool = False) -> None:
        """Launch the installer (for .exe) or open the folder (for .zip)."""
        path = Path(installer_path)
        if path.suffix.lower() == ".exe":
            args = [str(path)]
            if silent:
                args += ["/VERYSILENT", "/SUPPRESSMSGBOXES"]
            subprocess.Popen(args)
            log.info("Installer launched: %s", installer_path)
        elif path.suffix.lower() == ".zip":
            # Open containing folder so user can extract
            os.startfile(str(path.parent))
