import sqlite3

DATABASE = "finance.db"


def create_database():
    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            payment_method TEXT,
            date TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_database()
    print("Database created successfully!")