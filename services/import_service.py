"""
services/import_service.py — Data Import Service.

Handles importing from CSV, Excel, JSON, SQL dump, and another SQLite DB.
Supports column mapping, skip duplicates, upsert, batch insert, encoding detection.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Optional

from app.config import DEFAULT_BATCH_SIZE
from app.logger import get_logger

log = get_logger("import_service")


class ImportResult:
    def __init__(self, rows_imported: int, rows_skipped: int, errors: list[str]):
        self.rows_imported = rows_imported
        self.rows_skipped = rows_skipped
        self.errors = errors

    def __repr__(self):
        return f"<ImportResult imported={self.rows_imported} skipped={self.rows_skipped} errors={len(self.errors)}>"


class ImportService:
    """
    Import data into a SQLite table from various sources.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open database connection (not DatabaseConnection wrapper).
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # ── Main dispatcher ───────────────────────────────────────────────────────

    def import_file(
        self,
        path: str,
        table_name: str,
        *,
        column_map: Optional[dict[str, str]] = None,
        skip_duplicates: bool = False,
        upsert: bool = False,
        batch_size: int = DEFAULT_BATCH_SIZE,
        encoding: str = "utf-8",
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> ImportResult:
        """Auto-detect file type and import."""
        ext = Path(path).suffix.lower()
        if ext == ".csv":
            return self.import_csv(path, table_name, column_map=column_map,
                                   skip_duplicates=skip_duplicates, upsert=upsert,
                                   batch_size=batch_size, encoding=encoding,
                                   progress_cb=progress_cb)
        elif ext in (".xlsx", ".xls"):
            return self.import_excel(path, table_name, column_map=column_map,
                                     skip_duplicates=skip_duplicates, upsert=upsert,
                                     batch_size=batch_size, progress_cb=progress_cb)
        elif ext == ".json":
            return self.import_json(path, table_name, column_map=column_map,
                                    skip_duplicates=skip_duplicates, upsert=upsert,
                                    batch_size=batch_size, encoding=encoding,
                                    progress_cb=progress_cb)
        elif ext in (".sql", ".txt"):
            return self.import_sql_dump(path, encoding=encoding)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    # ── CSV ───────────────────────────────────────────────────────────────────

    def import_csv(
        self,
        path: str,
        table_name: str,
        *,
        column_map: Optional[dict[str, str]] = None,
        skip_duplicates: bool = False,
        upsert: bool = False,
        batch_size: int = DEFAULT_BATCH_SIZE,
        encoding: str = "utf-8",
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> ImportResult:
        log.info("Importing CSV: %s → %s", path, table_name)
        errors: list[str] = []
        imported = 0
        skipped = 0

        try:
            with open(path, newline="", encoding=encoding, errors="replace") as f:
                reader = csv.DictReader(f)
                all_rows = list(reader)

            total = len(all_rows)
            batch: list[tuple] = []
            cols: Optional[list[str]] = None

            for idx, row in enumerate(all_rows):
                mapped = self._map_columns(row, column_map)
                if cols is None:
                    cols = list(mapped.keys())
                values = tuple(mapped.get(c) for c in cols)
                batch.append(values)

                if len(batch) >= batch_size:
                    n, s, errs = self._insert_batch(table_name, cols, batch,
                                                     skip_duplicates=skip_duplicates, upsert=upsert)
                    imported += n; skipped += s; errors.extend(errs)
                    batch.clear()
                if progress_cb:
                    progress_cb(idx + 1, total)

            if batch and cols:
                n, s, errs = self._insert_batch(table_name, cols, batch,
                                                 skip_duplicates=skip_duplicates, upsert=upsert)
                imported += n; skipped += s; errors.extend(errs)

        except Exception as exc:
            log.error("CSV import failed: %s", exc)
            errors.append(str(exc))

        return ImportResult(imported, skipped, errors)

    # ── Excel ─────────────────────────────────────────────────────────────────

    def import_excel(
        self,
        path: str,
        table_name: str,
        *,
        sheet_name: Optional[str] = None,
        column_map: Optional[dict[str, str]] = None,
        skip_duplicates: bool = False,
        upsert: bool = False,
        batch_size: int = DEFAULT_BATCH_SIZE,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> ImportResult:
        log.info("Importing Excel: %s → %s", path, table_name)
        errors: list[str] = []
        imported = 0
        skipped = 0
        try:
            import pandas as pd
            df = pd.read_excel(path, sheet_name=sheet_name or 0, dtype=str)
            df = df.where(df.notna(), None)
            rows = df.to_dict("records")
            total = len(rows)
            cols: Optional[list[str]] = None
            batch: list[tuple] = []

            for idx, row in enumerate(rows):
                mapped = self._map_columns(row, column_map)
                if cols is None:
                    cols = list(mapped.keys())
                values = tuple(mapped.get(c) for c in cols)
                batch.append(values)
                if len(batch) >= batch_size:
                    n, s, errs = self._insert_batch(table_name, cols, batch,
                                                     skip_duplicates=skip_duplicates, upsert=upsert)
                    imported += n; skipped += s; errors.extend(errs)
                    batch.clear()
                if progress_cb:
                    progress_cb(idx + 1, total)

            if batch and cols:
                n, s, errs = self._insert_batch(table_name, cols, batch,
                                                 skip_duplicates=skip_duplicates, upsert=upsert)
                imported += n; skipped += s; errors.extend(errs)
        except Exception as exc:
            log.error("Excel import failed: %s", exc)
            errors.append(str(exc))

        return ImportResult(imported, skipped, errors)

    # ── JSON ──────────────────────────────────────────────────────────────────

    def import_json(
        self,
        path: str,
        table_name: str,
        *,
        column_map: Optional[dict[str, str]] = None,
        skip_duplicates: bool = False,
        upsert: bool = False,
        batch_size: int = DEFAULT_BATCH_SIZE,
        encoding: str = "utf-8",
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> ImportResult:
        log.info("Importing JSON: %s → %s", path, table_name)
        errors: list[str] = []
        imported = 0
        skipped = 0
        try:
            data = json.loads(Path(path).read_text(encoding))
            if isinstance(data, dict):
                # Try common keys like 'data', 'rows', 'results'
                for key in ("data", "rows", "results", "items"):
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
            if not isinstance(data, list):
                raise ValueError("JSON root must be an array of objects.")

            total = len(data)
            cols: Optional[list[str]] = None
            batch: list[tuple] = []

            for idx, row in enumerate(data):
                if not isinstance(row, dict):
                    continue
                mapped = self._map_columns(row, column_map)
                if cols is None:
                    cols = list(mapped.keys())
                values = tuple(str(mapped.get(c)) if mapped.get(c) is not None else None for c in cols)
                batch.append(values)
                if len(batch) >= batch_size:
                    n, s, errs = self._insert_batch(table_name, cols, batch,
                                                     skip_duplicates=skip_duplicates, upsert=upsert)
                    imported += n; skipped += s; errors.extend(errs)
                    batch.clear()
                if progress_cb:
                    progress_cb(idx + 1, total)

            if batch and cols:
                n, s, errs = self._insert_batch(table_name, cols, batch,
                                                 skip_duplicates=skip_duplicates, upsert=upsert)
                imported += n; skipped += s; errors.extend(errs)
        except Exception as exc:
            log.error("JSON import failed: %s", exc)
            errors.append(str(exc))

        return ImportResult(imported, skipped, errors)

    # ── SQL Dump ──────────────────────────────────────────────────────────────

    def import_sql_dump(self, path: str, encoding: str = "utf-8") -> ImportResult:
        log.info("Importing SQL dump: %s", path)
        try:
            script = Path(path).read_text(encoding)
            self._conn.executescript(script)
            return ImportResult(0, 0, [])
        except Exception as exc:
            log.error("SQL dump import failed: %s", exc)
            return ImportResult(0, 0, [str(exc)])

    # ── Import from another SQLite DB by query ────────────────────────────────

    def import_from_sqlite(
        self,
        source_path: str,
        source_query: str,
        target_table: str,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        skip_duplicates: bool = False,
        upsert: bool = False,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> ImportResult:
        log.info("Importing from SQLite: %s [%s] → %s", source_path, source_query[:60], target_table)
        errors: list[str] = []
        imported = 0
        skipped = 0
        try:
            src = sqlite3.connect(source_path)
            src.row_factory = sqlite3.Row
            cursor = src.execute(source_query)
            all_rows = cursor.fetchall()
            if not all_rows:
                return ImportResult(0, 0, [])
            cols = list(all_rows[0].keys())
            total = len(all_rows)
            batch: list[tuple] = []

            for idx, row in enumerate(all_rows):
                batch.append(tuple(row))
                if len(batch) >= batch_size:
                    n, s, errs = self._insert_batch(target_table, cols, batch,
                                                     skip_duplicates=skip_duplicates, upsert=upsert)
                    imported += n; skipped += s; errors.extend(errs)
                    batch.clear()
                if progress_cb:
                    progress_cb(idx + 1, total)

            if batch:
                n, s, errs = self._insert_batch(target_table, cols, batch,
                                                 skip_duplicates=skip_duplicates, upsert=upsert)
                imported += n; skipped += s; errors.extend(errs)
            src.close()
        except Exception as exc:
            log.error("SQLite import failed: %s", exc)
            errors.append(str(exc))

        return ImportResult(imported, skipped, errors)

    # ── Preview ───────────────────────────────────────────────────────────────

    def preview_file(self, path: str, rows: int = 5, encoding: str = "utf-8") -> tuple[list[str], list[list]]:
        """Return (headers, sample_rows) for preview before import."""
        ext = Path(path).suffix.lower()
        headers: list[str] = []
        sample: list[list] = []
        try:
            if ext == ".csv":
                with open(path, newline="", encoding=encoding, errors="replace") as f:
                    reader = csv.DictReader(f)
                    headers = reader.fieldnames or []
                    for i, row in enumerate(reader):
                        if i >= rows:
                            break
                        sample.append([row.get(h, "") for h in headers])
            elif ext in (".xlsx", ".xls"):
                import pandas as pd
                df = pd.read_excel(path, nrows=rows, dtype=str)
                headers = df.columns.tolist()
                sample = df.fillna("").values.tolist()
            elif ext == ".json":
                data = json.loads(Path(path).read_text(encoding))
                if isinstance(data, dict):
                    for key in ("data", "rows", "results", "items"):
                        if key in data:
                            data = data[key]
                            break
                if isinstance(data, list) and data:
                    headers = list(data[0].keys())
                    for row in data[:rows]:
                        sample.append([str(row.get(h, "")) for h in headers])
        except Exception as exc:
            log.warning("Preview failed: %s", exc)
        return headers, sample

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _map_columns(self, row: dict, column_map: Optional[dict]) -> dict:
        if not column_map:
            return row
        return {column_map.get(k, k): v for k, v in row.items() if column_map.get(k, k)}

    def _insert_batch(
        self,
        table: str,
        cols: list[str],
        batch: list[tuple],
        *,
        skip_duplicates: bool,
        upsert: bool,
    ) -> tuple[int, int, list[str]]:
        col_str = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join("?" for _ in cols)
        if upsert:
            sql = f'INSERT OR REPLACE INTO "{table}" ({col_str}) VALUES ({placeholders});'
        elif skip_duplicates:
            sql = f'INSERT OR IGNORE INTO "{table}" ({col_str}) VALUES ({placeholders});'
        else:
            sql = f'INSERT INTO "{table}" ({col_str}) VALUES ({placeholders});'
        errors = []
        imported = 0
        skipped = 0
        try:
            cur = self._conn.executemany(sql, batch)
            self._conn.commit()
            imported = cur.rowcount if cur.rowcount >= 0 else len(batch)
            if skip_duplicates or upsert:
                skipped = len(batch) - imported
        except Exception as exc:
            errors.append(str(exc))
            try:
                self._conn.rollback()
            except Exception:
                pass
        return imported, skipped, errors
