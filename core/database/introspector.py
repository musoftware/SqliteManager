"""
core/database/introspector.py — SQLite Schema Introspection.

Extracts tables, views, indexes, triggers, and column metadata
directly via SQLite's PRAGMA and sqlite_master table.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from app.logger import get_logger

log = get_logger("introspector")


@dataclass
class ColumnInfo:
    cid: int
    name: str
    type: str
    notnull: bool
    default_value: Optional[str]
    pk: int  # 0 = not PK, 1+ = PK order
    hidden: int = 0


@dataclass
class ForeignKeyInfo:
    id: int
    seq: int
    table: str
    from_col: str
    to_col: str
    on_update: str
    on_delete: str
    match: str


@dataclass
class IndexInfo:
    name: str
    unique: bool
    origin: str
    partial: bool
    columns: list[str] = field(default_factory=list)


@dataclass
class TableInfo:
    name: str
    type: str  # 'table' | 'view' | 'trigger' | 'index'
    sql: Optional[str] = None
    row_count: int = 0
    columns: list[ColumnInfo] = field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)


class SchemaIntrospector:
    """
    Reads schema information from an open sqlite3 connection.
    All methods are synchronous and should be called from a worker thread.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # ── Master lists ──────────────────────────────────────────────────────────

    def get_object_names(self, obj_type: str) -> list[str]:
        """Return names of all objects of given type (table|view|trigger|index)."""
        cur = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = ? AND name NOT LIKE 'sqlite_%' ORDER BY name;",
            (obj_type,),
        )
        return [row[0] for row in cur.fetchall()]

    def get_tables(self) -> list[str]:
        return self.get_object_names("table")

    def get_views(self) -> list[str]:
        return self.get_object_names("view")

    def get_indexes(self) -> list[str]:
        return self.get_object_names("index")

    def get_triggers(self) -> list[str]:
        return self.get_object_names("trigger")

    def get_all_objects(self) -> list[dict]:
        """Return all schema objects with type, name, sql."""
        cur = self._conn.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name;"
        )
        return [{"type": r[0], "name": r[1], "sql": r[2]} for r in cur.fetchall()]

    # ── Table details ─────────────────────────────────────────────────────────

    def get_columns(self, table_name: str) -> list[ColumnInfo]:
        cur = self._conn.execute(f"PRAGMA table_info({self._quote(table_name)});")
        cols = []
        for row in cur.fetchall():
            cols.append(
                ColumnInfo(
                    cid=row[0],
                    name=row[1],
                    type=row[2] or "TEXT",
                    notnull=bool(row[3]),
                    default_value=row[4],
                    pk=row[5],
                )
            )
        return cols

    def get_foreign_keys(self, table_name: str) -> list[ForeignKeyInfo]:
        cur = self._conn.execute(
            f"PRAGMA foreign_key_list({self._quote(table_name)});"
        )
        fks = []
        for row in cur.fetchall():
            fks.append(
                ForeignKeyInfo(
                    id=row[0],
                    seq=row[1],
                    table=row[2],
                    from_col=row[3],
                    to_col=row[4],
                    on_update=row[5],
                    on_delete=row[6],
                    match=row[7],
                )
            )
        return fks

    def get_indexes_for_table(self, table_name: str) -> list[IndexInfo]:
        cur = self._conn.execute(
            f"PRAGMA index_list({self._quote(table_name)});"
        )
        indexes = []
        for row in cur.fetchall():
            idx = IndexInfo(
                name=row[1],
                unique=bool(row[2]),
                origin=row[3],
                partial=bool(row[4]),
            )
            # Get columns for this index
            icur = self._conn.execute(f"PRAGMA index_info({self._quote(idx.name)});")
            idx.columns = [r[2] for r in icur.fetchall() if r[2]]
            indexes.append(idx)
        return indexes

    def get_row_count(self, table_name: str) -> int:
        try:
            cur = self._conn.execute(
                f"SELECT COUNT(*) FROM {self._quote(table_name)};"
            )
            return cur.fetchone()[0]
        except Exception:
            return 0

    def get_table_info(self, table_name: str) -> TableInfo:
        """Full table metadata in one call."""
        sql_row = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = ? AND type IN ('table','view');",
            (table_name,),
        ).fetchone()
        return TableInfo(
            name=table_name,
            type="table",
            sql=sql_row[0] if sql_row else None,
            row_count=self.get_row_count(table_name),
            columns=self.get_columns(table_name),
            foreign_keys=self.get_foreign_keys(table_name),
            indexes=self.get_indexes_for_table(table_name),
        )

    def get_view_info(self, view_name: str) -> TableInfo:
        sql_row = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = ? AND type = 'view';",
            (view_name,),
        ).fetchone()
        return TableInfo(
            name=view_name,
            type="view",
            sql=sql_row[0] if sql_row else None,
            row_count=self.get_row_count(view_name),
            columns=self.get_columns(view_name),
        )

    # ── Database-level ────────────────────────────────────────────────────────

    def get_database_stats(self) -> dict:
        """Return a dict of database-level statistics."""
        stats = {}
        try:
            stats["page_count"] = self._conn.execute("PRAGMA page_count;").fetchone()[0]
            stats["page_size"] = self._conn.execute("PRAGMA page_size;").fetchone()[0]
            stats["freelist_count"] = self._conn.execute("PRAGMA freelist_count;").fetchone()[0]
            stats["journal_mode"] = self._conn.execute("PRAGMA journal_mode;").fetchone()[0]
            stats["wal_autocheckpoint"] = self._conn.execute("PRAGMA wal_autocheckpoint;").fetchone()[0]
            stats["encoding"] = self._conn.execute("PRAGMA encoding;").fetchone()[0]
            stats["user_version"] = self._conn.execute("PRAGMA user_version;").fetchone()[0]
            stats["size_mb"] = round(
                stats["page_count"] * stats["page_size"] / (1024 * 1024), 2
            )
            stats["table_count"] = len(self.get_tables())
            stats["view_count"] = len(self.get_views())
            stats["index_count"] = len(self.get_indexes())
            stats["trigger_count"] = len(self.get_triggers())
        except Exception as exc:
            log.warning("Could not retrieve full DB stats: %s", exc)
        return stats

    def get_all_pragmas(self) -> dict:
        """Read commonly used PRAGMA values."""
        pragma_names = [
            "journal_mode", "synchronous", "foreign_keys", "cache_size",
            "page_size", "page_count", "auto_vacuum", "wal_autocheckpoint",
            "busy_timeout", "user_version", "encoding", "temp_store",
            "mmap_size", "locking_mode", "max_page_count",
        ]
        result = {}
        for name in pragma_names:
            try:
                row = self._conn.execute(f"PRAGMA {name};").fetchone()
                result[name] = row[0] if row else None
            except Exception:
                result[name] = None
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _quote(name: str) -> str:
        """Double-quote an identifier to handle spaces/reserved words."""
        return f'"{name}"'
