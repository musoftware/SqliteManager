"""
utils/demo_database.py — Creates a sample SQLite database for demonstration.

Generates a realistic e-commerce database with:
  - users, products, categories, orders, order_items
  - Indexes, foreign keys, and ~1000 rows of fake data
"""
from __future__ import annotations

import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta

from app.logger import get_logger

log = get_logger("demo_db")

DEMO_DB_PATH = Path(__file__).parent.parent / "demo_ecommerce.db"


def create_demo_database(path: str | None = None) -> str:
    """Create and populate the demo database. Returns the path."""
    db_path = path or str(DEMO_DB_PATH)
    log.info("Creating demo database: %s", db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")

    # ── Schema ────────────────────────────────────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL UNIQUE,
            slug      TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            phone      TEXT,
            city       TEXT,
            country    TEXT DEFAULT 'US',
            active     INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            name        TEXT NOT NULL,
            sku         TEXT UNIQUE,
            price       REAL NOT NULL,
            stock       INTEGER DEFAULT 0,
            active      INTEGER DEFAULT 1,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status      TEXT DEFAULT 'pending',
            total       REAL DEFAULT 0.0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            shipped_at  DATETIME
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id),
            qty        INTEGER NOT NULL DEFAULT 1,
            price      REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);
        CREATE INDEX IF NOT EXISTS idx_products_cat   ON products(category_id);
        CREATE INDEX IF NOT EXISTS idx_orders_user    ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_items_order    ON order_items(order_id);

        CREATE VIEW IF NOT EXISTS v_order_summary AS
        SELECT
            o.id,
            u.name  AS customer,
            u.email,
            o.status,
            o.total,
            o.created_at,
            COUNT(oi.id) AS item_count
        FROM orders o
        JOIN users u ON u.id = o.user_id
        LEFT JOIN order_items oi ON oi.order_id = o.id
        GROUP BY o.id;
    """)

    # ── Seed data ─────────────────────────────────────────────────────────────
    categories = [
        ("Electronics", "electronics"),
        ("Clothing", "clothing"),
        ("Books", "books"),
        ("Home & Garden", "home-garden"),
        ("Sports", "sports"),
        ("Toys", "toys"),
        ("Food & Beverages", "food"),
        ("Beauty", "beauty"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO categories (name, slug) VALUES (?, ?);", categories
    )

    # Users
    first_names = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
                   "Iris", "Jack", "Karen", "Leo", "Mia", "Noah", "Olivia", "Paul"]
    last_names = ["Smith", "Jones", "Williams", "Brown", "Davis", "Miller", "Wilson",
                  "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris"]
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
              "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Seattle"]
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "example.com"]

    users = []
    for i in range(1, 201):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        name = f"{fn} {ln}"
        email = f"{fn.lower()}.{ln.lower()}{i}@{random.choice(domains)}"
        phone = f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        city = random.choice(cities)
        active = 1 if random.random() > 0.1 else 0
        days_ago = random.randint(0, 730)
        created = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        users.append((name, email, phone, city, "US", active, created))

    conn.executemany(
        "INSERT OR IGNORE INTO users (name, email, phone, city, country, active, created_at) VALUES (?,?,?,?,?,?,?);",
        users,
    )

    # Products
    product_templates = [
        (1, "Smartphone Pro", 699.99), (1, "Laptop Ultra", 1299.99), (1, "Wireless Earbuds", 79.99),
        (1, "Smart Watch", 249.99), (1, "Tablet 10\"", 449.99), (1, "Bluetooth Speaker", 59.99),
        (2, "Cotton T-Shirt", 19.99), (2, "Jeans Classic", 49.99), (2, "Winter Jacket", 89.99),
        (2, "Sports Shoes", 79.99), (2, "Dress Shirt", 39.99),
        (3, "Python Programming", 34.99), (3, "Data Science Guide", 44.99), (3, "Clean Code", 29.99),
        (3, "Design Patterns", 39.99),
        (4, "Coffee Maker", 89.99), (4, "Plant Pot Set", 24.99), (4, "LED Lamp", 34.99),
        (5, "Yoga Mat", 29.99), (5, "Dumbbell Set", 79.99), (5, "Running Shoes", 99.99),
        (6, "LEGO Set", 59.99), (6, "Board Game", 34.99),
        (7, "Premium Coffee", 14.99), (7, "Organic Tea", 9.99),
        (8, "Face Cream", 24.99), (8, "Shampoo Set", 19.99),
    ]
    products = []
    for cat_id, pname, price in product_templates:
        sku = f"SKU-{cat_id:02d}-{random.randint(1000, 9999)}"
        stock = random.randint(0, 500)
        products.append((cat_id, pname, sku, price, stock, 1))

    conn.executemany(
        "INSERT OR IGNORE INTO products (category_id, name, sku, price, stock, active) VALUES (?,?,?,?,?,?);",
        products,
    )

    # Orders + items
    statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    status_weights = [0.1, 0.15, 0.2, 0.45, 0.1]
    product_ids = [r[0] for r in conn.execute("SELECT id, price FROM products;").fetchall()]
    product_prices = {r[0]: r[1] for r in conn.execute("SELECT id, price FROM products;").fetchall()}
    user_count = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]

    orders = []
    order_items = []
    for _ in range(500):
        user_id = random.randint(1, user_count)
        status = random.choices(statuses, weights=status_weights)[0]
        days_ago = random.randint(0, 365)
        created = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        shipped = None
        if status in ("shipped", "delivered"):
            shipped = (datetime.now() - timedelta(days=days_ago - 2)).strftime("%Y-%m-%d %H:%M:%S")
        orders.append((user_id, status, 0.0, created, shipped))

    conn.executemany(
        "INSERT INTO orders (user_id, status, total, created_at, shipped_at) VALUES (?,?,?,?,?);",
        orders,
    )

    order_ids = [r[0] for r in conn.execute("SELECT id FROM orders;").fetchall()]
    all_product_ids = [r[0] for r in conn.execute("SELECT id FROM products;").fetchall()]

    for order_id in order_ids:
        n_items = random.randint(1, 5)
        chosen = random.sample(all_product_ids, min(n_items, len(all_product_ids)))
        total = 0.0
        for pid in chosen:
            qty = random.randint(1, 4)
            price = product_prices.get(pid, 9.99)
            order_items.append((order_id, pid, qty, price))
            total += qty * price
        conn.execute(f"UPDATE orders SET total = ? WHERE id = ?;", (round(total, 2), order_id))

    conn.executemany(
        "INSERT INTO order_items (order_id, product_id, qty, price) VALUES (?,?,?,?);",
        order_items,
    )

    conn.commit()
    conn.close()
    log.info("Demo database created: %s", db_path)
    return db_path
