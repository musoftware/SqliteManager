"""
services/fake_data_service.py — Fake Test Data Generator.

Uses Faker to generate realistic test data matching column types.
"""
from __future__ import annotations

import random
import sqlite3
from typing import Any, Callable, Optional

from app.logger import get_logger

log = get_logger("fake_data")

# Type → Faker provider mapping
TYPE_FAKER_MAP: dict[str, str] = {
    "text": "text",
    "varchar": "word",
    "char": "word",
    "string": "word",
    "name": "name",
    "email": "email",
    "phone": "phone_number",
    "address": "address",
    "city": "city",
    "country": "country",
    "url": "url",
    "uuid": "uuid4",
    "integer": "random_int",
    "int": "random_int",
    "bigint": "random_int",
    "smallint": "random_int",
    "real": "pyfloat",
    "float": "pyfloat",
    "double": "pyfloat",
    "numeric": "pyfloat",
    "decimal": "pyfloat",
    "date": "date",
    "datetime": "date_time",
    "timestamp": "date_time",
    "boolean": "boolean",
    "bool": "boolean",
    "blob": "binary",
    "json": "json",
}


class FakeDataService:
    """Generate and insert fake test data into a SQLite table."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def generate(
        self,
        table: str,
        n_rows: int = 100,
        *,
        locale: str = "en_US",
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> int:
        """Generate n_rows of fake data into table. Returns rows inserted."""
        try:
            from faker import Faker
        except ImportError:
            raise RuntimeError("Please install 'faker': pip install faker")

        fake = Faker(locale)
        Faker.seed(42)

        # Get column info
        cur = self._conn.execute(f'PRAGMA table_info("{table}");')
        columns = cur.fetchall()
        if not columns:
            raise ValueError(f"Table '{table}' not found or has no columns.")

        # Filter out auto-increment PKs
        writable_cols = [c for c in columns if not (c[5] == 1 and "auto" in (c[2] or "").lower())]
        if not writable_cols:
            writable_cols = [c for c in columns if c[5] != 1]

        col_names = [c[1] for c in writable_cols]
        col_types = [c[2].lower() if c[2] else "text" for c in writable_cols]

        batch_size = 500
        inserted = 0
        batch: list[tuple] = []

        for i in range(n_rows):
            row = tuple(self._fake_value(fake, name, typ) for name, typ in zip(col_names, col_types))
            batch.append(row)
            if len(batch) >= batch_size:
                self._insert_batch(table, col_names, batch)
                inserted += len(batch)
                batch.clear()
            if progress_cb:
                progress_cb(i + 1, n_rows)

        if batch:
            self._insert_batch(table, col_names, batch)
            inserted += len(batch)

        log.info("Inserted %d fake rows into %s", inserted, table)
        return inserted

    def _fake_value(self, fake, col_name: str, col_type: str) -> Any:
        """Generate a fake value for a column by name/type heuristic."""
        name_lower = col_name.lower()
        # Name-based heuristics
        if "email" in name_lower:
            return fake.email()
        if "phone" in name_lower or "mobile" in name_lower:
            return fake.phone_number()
        if "name" in name_lower:
            return fake.name()
        if "first" in name_lower:
            return fake.first_name()
        if "last" in name_lower:
            return fake.last_name()
        if "address" in name_lower:
            return fake.address().replace("\n", ", ")
        if "city" in name_lower:
            return fake.city()
        if "country" in name_lower:
            return fake.country()
        if "zip" in name_lower or "postal" in name_lower:
            return fake.postcode()
        if "url" in name_lower or "website" in name_lower:
            return fake.url()
        if "uuid" in name_lower or "guid" in name_lower:
            return str(fake.uuid4())
        if "password" in name_lower or "hash" in name_lower:
            return fake.sha256()
        if "date" in name_lower and "time" not in name_lower:
            return fake.date()
        if "time" in name_lower or "created" in name_lower or "updated" in name_lower:
            return fake.date_time().strftime("%Y-%m-%d %H:%M:%S")
        if "price" in name_lower or "amount" in name_lower or "cost" in name_lower:
            return round(random.uniform(0.99, 9999.99), 2)
        if "count" in name_lower or "qty" in name_lower or "quantity" in name_lower:
            return random.randint(1, 1000)
        if "age" in name_lower:
            return random.randint(18, 85)
        if "active" in name_lower or "enabled" in name_lower or "status" in name_lower:
            return random.choice([0, 1])
        if "description" in name_lower or "notes" in name_lower or "comment" in name_lower:
            return fake.paragraph()

        # Type-based fallback
        t = col_type.split("(")[0].strip()
        if t in ("integer", "int", "bigint", "smallint", "tinyint"):
            return random.randint(1, 100000)
        if t in ("real", "float", "double", "numeric", "decimal"):
            return round(random.uniform(0, 10000), 4)
        if t in ("boolean", "bool"):
            return random.choice([0, 1])
        if t == "date":
            return fake.date()
        if t in ("datetime", "timestamp"):
            return fake.date_time().strftime("%Y-%m-%d %H:%M:%S")
        if t == "blob":
            return fake.binary(length=16)
        # Default: text/varchar/char
        return fake.word()

    def _insert_batch(self, table: str, cols: list[str], batch: list[tuple]) -> None:
        col_str = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join("?" for _ in cols)
        sql = f'INSERT OR IGNORE INTO "{table}" ({col_str}) VALUES ({placeholders});'
        self._conn.executemany(sql, batch)
        self._conn.commit()
