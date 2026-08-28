import sqlite3

connection = sqlite3.connect("finance.db")

connection.execute("""
    INSERT INTO transactions
    (amount, type, category, description, payment_method, date)
    VALUES (?, ?, ?, ?, ?, ?)
""", (
    10000,
    "income",
    "Freelance",
    "Website work",
    "M-Pesa",
    "2026-08-28"
))

connection.commit()
connection.close()

print("Test transaction added!")