"""
services/export_service.py — Data Export Service.

Exports to CSV, Excel, JSON, SQL dump, PDF report, and another SQLite DB.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any, Callable, Optional

from app.logger import get_logger

log = get_logger("export_service")


class ExportService:
    """Export data from a SQLite connection to various formats."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # ── Main dispatcher ───────────────────────────────────────────────────────

    def export(
        self,
        path: str,
        table: Optional[str] = None,
        sql: Optional[str] = None,
        *,
        compress: bool = False,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """Export table or SQL query result to file. Returns output path."""
        ext = Path(path).suffix.lower()
        if sql:
            headers, rows = self._fetch_by_sql(sql)
        elif table:
            headers, rows = self._fetch_table(table)
        else:
            raise ValueError("Must provide either table or sql.")

        if ext == ".csv":
            self._to_csv(path, headers, rows, progress_cb=progress_cb)
        elif ext in (".xlsx", ".xls"):
            self._to_excel(path, headers, rows, progress_cb=progress_cb)
        elif ext == ".json":
            self._to_json(path, headers, rows, progress_cb=progress_cb)
        elif ext == ".sql":
            if table:
                self._to_sql_dump(path, table, progress_cb=progress_cb)
            else:
                self._generic_sql_dump(path, headers, rows, table_name="export")
        elif ext == ".pdf":
            self._to_pdf(path, headers, rows, title=table or "Query Result")
        elif ext == ".db":
            self._to_sqlite(path, headers, rows, table_name=table or "export")
        else:
            raise ValueError(f"Unsupported export format: {ext}")

        if compress:
            zip_path = path + ".zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(path, Path(path).name)
            return zip_path

        return path

    # ── Formats ───────────────────────────────────────────────────────────────

    def _to_csv(self, path: str, headers: list[str], rows: list[tuple],
                encoding: str = "utf-8",
                progress_cb: Optional[Callable] = None) -> None:
        with open(path, "w", newline="", encoding=encoding) as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            total = len(rows)
            for i, row in enumerate(rows):
                writer.writerow(["" if v is None else v for v in row])
                if progress_cb:
                    progress_cb(i + 1, total)
        log.info("Exported CSV: %s (%d rows)", path, len(rows))

    def _to_excel(self, path: str, headers: list[str], rows: list[tuple],
                  progress_cb: Optional[Callable] = None) -> None:
        import pandas as pd
        df = pd.DataFrame(rows, columns=headers)
        df.to_excel(path, index=False)
        log.info("Exported Excel: %s (%d rows)", path, len(rows))

    def _to_json(self, path: str, headers: list[str], rows: list[tuple],
                 encoding: str = "utf-8",
                 progress_cb: Optional[Callable] = None) -> None:
        data = []
        total = len(rows)
        for i, row in enumerate(rows):
            data.append(dict(zip(headers, ["" if v is None else v for v in row])))
            if progress_cb:
                progress_cb(i + 1, total)
        Path(path).write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding)
        log.info("Exported JSON: %s (%d rows)", path, len(rows))

    def _to_sql_dump(self, path: str, table: str,
                     progress_cb: Optional[Callable] = None) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for line in self._conn.iterdump():
                if table.lower() in line.lower():
                    f.write(line + "\n")
        log.info("Exported SQL dump: %s", path)

    def _generic_sql_dump(self, path: str, headers: list[str], rows: list[tuple],
                          table_name: str = "export") -> None:
        col_def = ", ".join(f'"{h}" TEXT' for h in headers)
        lines = [f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_def});']
        col_str = ", ".join(f'"{h}"' for h in headers)
        for row in rows:
            vals = ", ".join(
                "NULL" if v is None else f"'{str(v).replace(chr(39), chr(39)*2)}'"
                for v in row
            )
            lines.append(f'INSERT INTO "{table_name}" ({col_str}) VALUES ({vals});')
        Path(path).write_text("\n".join(lines), "utf-8")

    def _to_pdf(self, path: str, headers: list[str], rows: list[tuple],
                title: str = "Export") -> None:
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors

            doc = SimpleDocTemplate(path, pagesize=landscape(A4))
            styles = getSampleStyleSheet()
            elements = [Paragraph(title, styles["Title"])]

            table_data = [headers] + [[("" if v is None else str(v)) for v in row] for row in rows[:5000]]
            t = Table(table_data, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e1e2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#cba6f7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f0f0f8")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(t)
            doc.build(elements)
            log.info("Exported PDF: %s", path)
        except ImportError:
            log.error("reportlab not installed for PDF export.")
            raise

    def _to_sqlite(self, path: str, headers: list[str], rows: list[tuple],
                   table_name: str = "export") -> None:
        dest = sqlite3.connect(path)
        col_def = ", ".join(f'"{h}" TEXT' for h in headers)
        dest.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_def});')
        col_str = ", ".join(f'"{h}"' for h in headers)
        placeholders = ", ".join("?" for _ in headers)
        dest.executemany(
            f'INSERT INTO "{table_name}" ({col_str}) VALUES ({placeholders});',
            [tuple("" if v is None else v for v in row) for row in rows]
        )
        dest.commit()
        dest.close()
        log.info("Exported to SQLite: %s", path)

    # ── Fetch helpers ─────────────────────────────────────────────────────────

    def _fetch_table(self, table: str) -> tuple[list[str], list[tuple]]:
        cur = self._conn.execute(f'SELECT * FROM "{table}";')
        headers = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return headers, [tuple(r) for r in rows]

    def _fetch_by_sql(self, sql: str) -> tuple[list[str], list[tuple]]:
        cur = self._conn.execute(sql)
        headers = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return headers, [tuple(r) for r in rows]
