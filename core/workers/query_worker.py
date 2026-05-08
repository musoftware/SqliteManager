"""
core/workers/query_worker.py — Background Query Execution Worker.

Runs SQL statements in a QThread so the UI never freezes.
Emits progress signals to update status bar and result panels.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Optional

from PySide6.QtCore import QThread, Signal

from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.executor import QueryResult, SqlExecutor

log = get_logger("query_worker")


class QueryWorker(QThread):
    """
    Execute one or more SQL statements in a background thread.

    Signals
    -------
    result_ready(QueryResult)     — one result set is ready
    row_count_changed(int)        — total rows emitted after query
    error(str)                    — error message
    message(str)                  — informational message (non-error)
    finished(float)               — elapsed ms when all done
    progress(int, int)            — current, total (for multi-statement scripts)
    """

    result_ready = Signal(object)          # QueryResult
    error = Signal(str)
    message = Signal(str)
    finished = Signal(float)              # elapsed_ms
    progress = Signal(int, int)           # current, total statements

    def __init__(
        self,
        conn: DatabaseConnection,
        sql: str,
        params: tuple = (),
        *,
        timeout: float = 30.0,
        explain: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._conn = conn
        self._sql = sql
        self._params = params
        self._timeout = timeout
        self._explain = explain
        self._cancelled = False

    def cancel(self) -> None:
        """Signal the worker to stop after the current statement."""
        self._cancelled = True
        self._conn.connection.interrupt()   # Interrupt ongoing SQLite op
        log.info("Query cancelled by user.")

    def run(self) -> None:
        executor = SqlExecutor(self._conn)
        t0 = time.perf_counter()

        # Split multi-statement scripts
        statements = self._split_statements(self._sql)
        total = len(statements)

        for idx, stmt in enumerate(statements):
            if self._cancelled:
                self.message.emit("Query cancelled.")
                break

            stmt = stmt.strip()
            if not stmt:
                continue

            self.progress.emit(idx + 1, total)

            try:
                if self._explain:
                    result = executor.explain_query(stmt)
                else:
                    result = executor.execute_query(stmt, self._params, timeout=self._timeout)
                    # Commit if it was a write statement
                    if result.rowcount >= 0 and not stmt.upper().startswith("SELECT"):
                        try:
                            self._conn.commit()
                        except Exception:
                            pass

                self.result_ready.emit(result)

            except sqlite3.OperationalError as exc:
                self.error.emit(f"SQL Error: {exc}\n\nStatement:\n{stmt}")
                log.error("Query error: %s", exc)
                return
            except Exception as exc:
                self.error.emit(f"Unexpected error: {exc}")
                log.exception("Unexpected query error")
                return

        elapsed = (time.perf_counter() - t0) * 1000
        self.finished.emit(elapsed)

    @staticmethod
    def _split_statements(sql: str) -> list[str]:
        """Split a SQL script into individual statements by semicolon."""
        try:
            import sqlparse
            return [str(s) for s in sqlparse.parse(sql) if str(s).strip()]
        except ImportError:
            # Fallback: naive split on ';'
            return [s for s in sql.split(";") if s.strip()]


class SchemaLoadWorker(QThread):
    """Load full schema in background and emit when done."""

    schema_loaded = Signal(dict)   # {tables: [], views: [], indexes: [], triggers: []}
    error = Signal(str)

    def __init__(self, conn: DatabaseConnection, parent=None):
        super().__init__(parent)
        self._conn = conn

    def run(self) -> None:
        from core.database.introspector import SchemaIntrospector
        try:
            intro = SchemaIntrospector(self._conn.connection)
            schema = {
                "tables": intro.get_tables(),
                "views": intro.get_views(),
                "indexes": intro.get_indexes(),
                "triggers": intro.get_triggers(),
            }
            self.schema_loaded.emit(schema)
        except Exception as exc:
            self.error.emit(str(exc))
            log.exception("Schema load error")
