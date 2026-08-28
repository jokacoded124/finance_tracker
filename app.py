import csv
import io
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash, Response

from database import get_db_connection

app = Flask(__name__)
app.secret_key = "change-this-to-a-random-secret-key"  # needed for flash messages


# =========================
# HOME / DASHBOARD
# =========================

@app.route("/")
def home():

    connection = get_db_connection()

    today = date.today()
    current_month = today.strftime("%Y-%m")

    # Optional filters from query string (search box on dashboard)
    search_term = request.args.get("q", "").strip()
    type_filter = request.args.get("type", "").strip()  # "income" / "expense" / ""

    query = """
        SELECT *
        FROM transactions
        WHERE date LIKE ?
    """
    params = [current_month + "%"]

    if type_filter in ("income", "expense"):
        query += " AND type = ?"
        params.append(type_filter)

    if search_term:
        query += " AND (category LIKE ? OR description LIKE ?)"
        like_term = f"%{search_term}%"
        params.extend([like_term, like_term])

    query += " ORDER BY date DESC, id DESC"

    # Transactions for the current month (filtered)
    transactions = connection.execute(query, params).fetchall()

    # Income for this month
    total_income = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE type = 'income'
        AND date LIKE ?
    """, (current_month + "%",)).fetchone()[0]

    # Expenses for this month
    total_expenses = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE type = 'expense'
        AND date LIKE ?
    """, (current_month + "%",)).fetchone()[0]

    balance = total_income - total_expenses

    # This month's budget
    budget_result = connection.execute("""
        SELECT amount
        FROM budgets
        WHERE month = ?
    """, (current_month,)).fetchone()

    monthly_budget = budget_result["amount"] if budget_result else 0
    remaining_budget = monthly_budget - total_expenses

    if monthly_budget > 0:
        budget_percentage = (total_expenses / monthly_budget) * 100
    else:
        budget_percentage = 0

    # Spending broken down by category (for this month) - used for a simple breakdown
    category_breakdown = connection.execute("""
        SELECT category, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE type = 'expense'
        AND date LIKE ?
        GROUP BY category
        ORDER BY total DESC
    """, (current_month + "%",)).fetchall()

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
        budget_percentage=min(budget_percentage, 100),
        category_breakdown=category_breakdown,
        search_term=search_term,
        type_filter=type_filter,
    )


# =========================
# MONTHLY HISTORY
# =========================

@app.route("/history")
def history():

    connection = get_db_connection()

    # Income and expenses grouped by month, most recent first (last 12 months of data)
    rows = connection.execute("""
        SELECT
            substr(date, 1, 7) AS month,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS expenses
        FROM transactions
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
    """).fetchall()

    connection.close()

    months = []
    max_value = 0.01  # avoid divide-by-zero
    for row in rows:
        income = row["income"] or 0
        expenses = row["expenses"] or 0
        max_value = max(max_value, income, expenses)
        months.append({
            "month": row["month"],
            "income": income,
            "expenses": expenses,
            "net": income - expenses,
        })

    return render_template("history.html", months=months, max_value=max_value)


# =========================
# EXPORT TO CSV
# =========================

@app.route("/export-csv")
def export_csv():

    connection = get_db_connection()

    rows = connection.execute("""
        SELECT date, type, category, description, payment_method, amount
        FROM transactions
        ORDER BY date DESC, id DESC
    """).fetchall()

    connection.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Type", "Category", "Description", "Payment Method", "Amount"])

    for row in rows:
        writer.writerow([
            row["date"],
            row["type"],
            row["category"],
            row["description"] or "",
            row["payment_method"] or "",
            row["amount"],
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
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

    flash("Transaction deleted.", "success")
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

        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        transaction_date = request.form.get("date", "").strip()

        error = validate_transaction_input(amount, category, transaction_date)
        if error:
            connection.close()
            flash(error, "error")
            return render_template("edit_transaction.html", transaction=transaction)

        connection.execute("""
            UPDATE transactions
            SET amount = ?,
                category = ?,
                description = ?,
                payment_method = ?,
                date = ?
            WHERE id = ?
        """, (
            float(amount),
            category,
            description,
            payment_method,
            transaction_date,
            transaction_id
        ))

        connection.commit()
        connection.close()

        flash("Transaction updated.", "success")
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

        amount = request.form.get("amount", "").strip()
        source = request.form.get("source", "").strip()
        description = request.form.get("description", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        transaction_date = request.form.get("date", "").strip()

        error = validate_transaction_input(amount, source, transaction_date)
        if error:
            flash(error, "error")
            return render_template("add_income.html")

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO transactions
            (amount, type, category, description, payment_method, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            float(amount),
            "income",
            source,
            description,
            payment_method,
            transaction_date
        ))

        connection.commit()
        connection.close()

        flash("Income added.", "success")
        return redirect(url_for("home"))

    return render_template("add_income.html", today=date.today().isoformat())


# =========================
# ADD EXPENSE
# =========================

@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():

    if request.method == "POST":

        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        transaction_date = request.form.get("date", "").strip()

        error = validate_transaction_input(amount, category, transaction_date)
        if error:
            flash(error, "error")
            return render_template("add_expense.html")

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO transactions
            (amount, type, category, description, payment_method, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            float(amount),
            "expense",
            category,
            description,
            payment_method,
            transaction_date
        ))

        connection.commit()
        connection.close()

        flash("Expense added.", "success")
        return redirect(url_for("home"))

    return render_template("add_expense.html", today=date.today().isoformat())


# =========================
# SET MONTHLY BUDGET
# =========================

@app.route("/set-budget", methods=["GET", "POST"])
def set_budget():

    today = date.today()
    current_month = today.strftime("%Y-%m")

    connection = get_db_connection()

    if request.method == "POST":

        amount = request.form.get("amount", "").strip()

        if not amount or not is_positive_number(amount):
            connection.close()
            flash("Please enter a valid budget amount.", "error")
            return redirect(url_for("set_budget"))

        connection.execute("""
            INSERT INTO budgets (month, amount)
            VALUES (?, ?)
            ON CONFLICT(month)
            DO UPDATE SET amount = excluded.amount
        """, (current_month, float(amount)))

        connection.commit()
        connection.close()

        flash("Budget updated.", "success")
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


# =========================
# HELPERS
# =========================

def is_positive_number(value):
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def validate_transaction_input(amount, category, transaction_date):
    """Return an error message string if input is invalid, otherwise None."""
    if not is_positive_number(amount):
        return "Please enter a valid amount greater than 0."
    if not category:
        return "Please choose a category."
    if not transaction_date:
        return "Please choose a date."
    return None


if __name__ == "__main__":
    app.run(debug=True)
