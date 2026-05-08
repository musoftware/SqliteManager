"""
core/database/executor.py — Synchronous SQL Executor.

Provides high-level, safe SQL execution methods used by both
the data viewer and the query editor.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Any, Optional

from app.logger import get_logger
from core.database.connection import DatabaseConnection

log = get_logger("executor")


class QueryResult:
    """Container for a completed query execution result."""

    def __init__(
        self,
        columns: list[str],
        rows: list[tuple],
        rowcount: int,
        elapsed_ms: float,
        sql: str,
    ):
        self.columns = columns
        self.rows = rows
        self.rowcount = rowcount
        self.elapsed_ms = elapsed_ms
        self.sql = sql

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def __repr__(self) -> str:
        return (
            f"<QueryResult cols={len(self.columns)} rows={self.row_count} "
            f"elapsed={self.elapsed_ms:.1f}ms>"
        )


class SqlExecutor:
    """
    Wraps a DatabaseConnection with high-level query helpers.
    All methods are synchronous — call from a background thread.
    """

    def __init__(self, conn: DatabaseConnection):
        self._conn = conn

    # ── Core execute ──────────────────────────────────────────────────────────

    def execute_query(
        self,
        sql: str,
        params: tuple = (),
        *,
        timeout: float = 30.0,
    ) -> QueryResult:
        """Execute a SELECT or other single statement, return QueryResult."""
        t0 = time.perf_counter()
        cursor = self._conn.execute(sql, params, timeout=timeout)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if cursor.description:
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
            rows = [tuple(r) for r in rows]
        else:
            columns = []
            rows = []

        return QueryResult(
            columns=columns,
            rows=rows,
            rowcount=cursor.rowcount,
            elapsed_ms=elapsed_ms,
            sql=sql,
        )

    def execute_write(
        self,
        sql: str,
        params: tuple = (),
        *,
        commit: bool = True,
        timeout: float = 30.0,
    ) -> int:
        """Execute INSERT/UPDATE/DELETE. Returns affected row count."""
        cursor = self._conn.execute(sql, params, timeout=timeout)
        if commit:
            self._conn.commit()
        return cursor.rowcount

    def execute_script(self, script: str) -> None:
        """Execute a multi-statement SQL script."""
        self._conn.executescript(script)
        self._conn.commit()

    def execute_many(
        self,
        sql: str,
        data: list[tuple],
        *,
        commit: bool = True,
    ) -> int:
        """Execute parameterised statement for many rows. Returns rowcount."""
        cursor = self._conn.executemany(sql, data)
        if commit:
            self._conn.commit()
        return cursor.rowcount

    # ── Paged fetch ───────────────────────────────────────────────────────────

    def fetch_page(
        self,
        table: str,
        page: int = 0,
        page_size: int = 500,
        order_col: Optional[str] = None,
        order_asc: bool = True,
        filters: Optional[dict[str, str]] = None,
    ) -> QueryResult:
        """
        Fetch one page of rows from *table* using LIMIT/OFFSET.
        Supports optional ORDER BY and per-column WHERE filters.
        """
        where_clause = ""
        params: list[Any] = []

        if filters:
            conditions = []
            for col, val in filters.items():
                if val:
                    conditions.append(f'"{col}" LIKE ?')
                    params.append(f"%{val}%")
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

        order_clause = ""
        if order_col:
            direction = "ASC" if order_asc else "DESC"
            order_clause = f'ORDER BY "{order_col}" {direction}'

        sql = (
            f'SELECT * FROM "{table}" {where_clause} {order_clause} '
            f"LIMIT {page_size} OFFSET {page * page_size};"
        )
        params += []
        return self.execute_query(sql, tuple(params))

    def count_rows(
        self,
        table: str,
        filters: Optional[dict[str, str]] = None,
    ) -> int:
        """Count rows in table, applying the same filters as fetch_page."""
        where_clause = ""
        params: list[Any] = []

        if filters:
            conditions = []
            for col, val in filters.items():
                if val:
                    conditions.append(f'"{col}" LIKE ?')
                    params.append(f"%{val}%")
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

        sql = f'SELECT COUNT(*) FROM "{table}" {where_clause};'
        cur = self._conn.execute(sql, tuple(params))
        return cur.fetchone()[0]

    # ── Row operations ────────────────────────────────────────────────────────

    def insert_row(self, table: str, row_data: dict[str, Any]) -> int:
        """Insert a dict of {column: value} into table."""
        cols = ", ".join(f'"{c}"' for c in row_data.keys())
        placeholders = ", ".join("?" for _ in row_data)
        sql = f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders});'
        return self.execute_write(sql, tuple(row_data.values()))

    def update_row(
        self,
        table: str,
        pk_col: str,
        pk_val: Any,
        updates: dict[str, Any],
    ) -> int:
        """Update a single row identified by primary key."""
        set_clause = ", ".join(f'"{c}" = ?' for c in updates.keys())
        sql = f'UPDATE "{table}" SET {set_clause} WHERE "{pk_col}" = ?;'
        return self.execute_write(sql, (*updates.values(), pk_val))

    def delete_rows(self, table: str, pk_col: str, pk_vals: list[Any]) -> int:
        """Delete rows by primary key list."""
        placeholders = ", ".join("?" for _ in pk_vals)
        sql = f'DELETE FROM "{table}" WHERE "{pk_col}" IN ({placeholders});'
        return self.execute_write(sql, tuple(pk_vals))

    # ── Explain ───────────────────────────────────────────────────────────────

    def explain_query(self, sql: str) -> QueryResult:
        return self.execute_query(f"EXPLAIN QUERY PLAN {sql}")
