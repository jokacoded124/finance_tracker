"""
Run this once on your EXISTING database (local or on PythonAnywhere) to add
the new tables needed for per-category budgets and recurring transactions,
without touching any of your existing transactions or budget data.

    python migrate.py

Safe to run multiple times.
"""

import sqlite3

DATABASE = "finance.db"

connection = sqlite3.connect(DATABASE)

connection.execute("""
    CREATE TABLE IF NOT EXISTS category_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        month TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        UNIQUE(month, category)
    )
""")

connection.execute("""
    CREATE TABLE IF NOT EXISTS recurring_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
        category TEXT NOT NULL,
        description TEXT,
        payment_method TEXT,
        day_of_month INTEGER NOT NULL CHECK(day_of_month BETWEEN 1 AND 28),
        active INTEGER NOT NULL DEFAULT 1,
        last_added_month TEXT
    )
""")

connection.commit()
connection.close()

print("Migration complete: category_budgets and recurring_transactions tables are ready.")
