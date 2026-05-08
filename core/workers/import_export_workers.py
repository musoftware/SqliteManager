"""
core/workers/import_worker.py — Background Import Worker.
core/workers/export_worker.py — Background Export Worker.
Combined in one file for organisation.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class ImportWorker(QThread):
    """Run import operations in a background thread."""

    progress = Signal(int, int, str)   # current, total, message
    finished = Signal(int)             # rows imported
    error = Signal(str)

    def __init__(self, import_func, *args, **kwargs):
        super().__init__()
        self._func = import_func
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result if isinstance(result, int) else 0)
        except Exception as exc:
            self.error.emit(str(exc))


class ExportWorker(QThread):
    """Run export operations in a background thread."""

    progress = Signal(int, int, str)
    finished = Signal(str)   # output path
    error = Signal(str)

    def __init__(self, export_func, *args, **kwargs):
        super().__init__()
        self._func = export_func
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result or "")
        except Exception as exc:
            self.error.emit(str(exc))
