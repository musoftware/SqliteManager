"""
services/formatter_service.py — SQL Formatter Service.
"""
from __future__ import annotations

from app.logger import get_logger

log = get_logger("formatter")


class SqlFormatterService:
    """Wraps sqlparse to format SQL statements."""

    @staticmethod
    def format(sql: str, *, uppercase_keywords: bool = True) -> str:
        try:
            import sqlparse
            return sqlparse.format(
                sql,
                reindent=True,
                reindent_aligned=False,
                keyword_case="upper" if uppercase_keywords else "lower",
                identifier_case="lower",
                strip_comments=False,
                use_space_around_operators=True,
            )
        except ImportError:
            log.warning("sqlparse not installed.")
            return sql

    @staticmethod
    def minify(sql: str) -> str:
        """Strip extra whitespace from SQL."""
        try:
            import sqlparse
            return sqlparse.format(sql, strip_whitespace=True)
        except ImportError:
            import re
            return re.sub(r"\s+", " ", sql).strip()

    @staticmethod
    def split_statements(sql: str) -> list[str]:
        """Split multi-statement SQL script into individual statements."""
        try:
            import sqlparse
            return [str(s).strip() for s in sqlparse.parse(sql) if str(s).strip()]
        except ImportError:
            return [s.strip() for s in sql.split(";") if s.strip()]
