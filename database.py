import sqlite3

DATABASE = "finance.db"


def get_db_connection():
    """Create and return a database connection with row access by column name."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    # Enforce foreign key constraints (off by default in SQLite)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
