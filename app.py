from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

DATABASE = "finance.db"


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection

@app.route("/")
def home():

    connection = get_db_connection()

    # Get the current year and month
    from datetime import date

    today = date.today()
    current_month = today.strftime("%Y-%m")

    # Get transactions for the current month
    transactions = connection.execute("""
        SELECT *
        FROM transactions
        WHERE date LIKE ?
        ORDER BY date DESC, id DESC
    """, (current_month + "%",)).fetchall()

    # Calculate income for this month
    total_income = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE type = 'income'
        AND date LIKE ?
    """, (current_month + "%",)).fetchone()[0]

    # Calculate expenses for this month
    total_expenses = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE type = 'expense'
        AND date LIKE ?
    """, (current_month + "%",)).fetchone()[0]

    # Calculate balance
    balance = total_income - total_expenses

    # Get this month's budget
    budget_result = connection.execute("""
        SELECT amount
        FROM budgets
        WHERE month = ?
    """, (current_month,)).fetchone()

    monthly_budget = budget_result["amount"] if budget_result else 0

    # Calculate remaining budget
    remaining_budget = monthly_budget - total_expenses

    # Calculate budget percentage
    if monthly_budget > 0:
        budget_percentage = (total_expenses / monthly_budget) * 100
    else:
        budget_percentage = 0

    # Display month name
    month_name = today.strftime("%B %Y")

    connection.close()

    return render_template(
        "dashboard.html",
        transactions=transactions,
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        month_name=month_name,
        monthly_budget=monthly_budget,
        remaining_budget=remaining_budget,
        budget_percentage=budget_percentage
    )
# =========================
# DELETE TRANSACTION
# =========================

@app.route("/delete-transaction/<int:transaction_id>", methods=["POST"])
def delete_transaction(transaction_id):

    connection = get_db_connection()

    connection.execute("""
        DELETE FROM transactions
        WHERE id = ?
    """, (transaction_id,))

    connection.commit()
    connection.close()

    return redirect(url_for("home"))


# =========================
# EDIT TRANSACTION
# =========================

@app.route("/edit-transaction/<int:transaction_id>", methods=["GET", "POST"])
def edit_transaction(transaction_id):

    connection = get_db_connection()

    transaction = connection.execute("""
        SELECT *
        FROM transactions
        WHERE id = ?
    """, (transaction_id,)).fetchone()

    if transaction is None:
        connection.close()
        return "Transaction not found", 404

    if request.method == "POST":

        amount = request.form["amount"]
        category = request.form["category"]
        description = request.form["description"]
        payment_method = request.form["payment_method"]
        date = request.form["date"]

        connection.execute("""
            UPDATE transactions
            SET amount = ?,
                category = ?,
                description = ?,
                payment_method = ?,
                date = ?
            WHERE id = ?
        """, (
            amount,
            category,
            description,
            payment_method,
            date,
            transaction_id
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("home"))

    connection.close()

    return render_template(
        "edit_transaction.html",
        transaction=transaction
    )


# =========================
# ADD INCOME
# =========================

@app.route("/add-income", methods=["GET", "POST"])
def add_income():

    if request.method == "POST":

        amount = request.form["amount"]
        source = request.form["source"]
        description = request.form["description"]
        payment_method = request.form["payment_method"]
        date = request.form["date"]

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO transactions
            (amount, type, category, description, payment_method, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            amount,
            "income",
            source,
            description,
            payment_method,
            date
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("home"))

    return render_template("add_income.html")


# =========================
# ADD EXPENSE
# =========================

@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():

    if request.method == "POST":

        amount = request.form["amount"]
        category = request.form["category"]
        description = request.form["description"]
        payment_method = request.form["payment_method"]
        date = request.form["date"]

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO transactions
            (amount, type, category, description, payment_method, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            amount,
            "expense",
            category,
            description,
            payment_method,
            date
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("home"))

    return render_template("add_expense.html")
# =========================
# SET MONTHLY BUDGET
# =========================

@app.route("/set-budget", methods=["GET", "POST"])
def set_budget():

    from datetime import date

    today = date.today()
    current_month = today.strftime("%Y-%m")

    connection = get_db_connection()

    if request.method == "POST":

        amount = request.form["amount"]

        connection.execute("""
            INSERT INTO budgets (month, amount)
            VALUES (?, ?)
            ON CONFLICT(month)
            DO UPDATE SET amount = excluded.amount
        """, (current_month, amount))

        connection.commit()
        connection.close()

        return redirect(url_for("home"))

    budget = connection.execute("""
        SELECT *
        FROM budgets
        WHERE month = ?
    """, (current_month,)).fetchone()

    connection.close()

    return render_template(
        "set_budget.html",
        budget=budget,
        month_name=today.strftime("%B %Y")
    )

if __name__ == "__main__":
    app.run(debug=True)