import csv
import io
import os
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import check_password_hash

from database import get_db_connection

app = Flask(__name__)

# Secret key — used to sign session cookies. Set via environment variable in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Single-user login credentials, set via environment variables.
# See generate_password_hash.py to create APP_PASSWORD_HASH.
APP_USERNAME = os.environ.get("APP_USERNAME", "admin")
APP_PASSWORD_HASH = os.environ.get("APP_PASSWORD_HASH", "")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    """Single hardcoded user — id is always '1'."""
    id = "1"


@login_manager.user_loader
def load_user(user_id):
    if user_id == "1":
        return User()
    return None


# =========================
# LOGIN / LOGOUT
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        valid_username = username == APP_USERNAME
        valid_password = bool(APP_PASSWORD_HASH) and check_password_hash(APP_PASSWORD_HASH, password)

        if valid_username and valid_password:
            login_user(User(), remember=True)
            flash("Welcome back!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("home"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


# =========================
# HOME / DASHBOARD
# =========================

@app.route("/")
@login_required
def home():

    connection = get_db_connection()

    today = date.today()
    current_month = today.strftime("%Y-%m")

    apply_due_recurring_transactions(connection, today)

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

    # Per-category budgets for this month, joined with actual spend
    category_budget_rows = connection.execute("""
        SELECT category, amount
        FROM category_budgets
        WHERE month = ?
    """, (current_month,)).fetchall()

    spend_by_category = {row["category"]: row["total"] for row in category_breakdown}

    category_budgets = []
    for row in category_budget_rows:
        spent = spend_by_category.get(row["category"], 0)
        limit = row["amount"]
        percentage = min((spent / limit * 100) if limit > 0 else 0, 100)
        category_budgets.append({
            "category": row["category"],
            "limit": limit,
            "spent": spent,
            "remaining": limit - spent,
            "percentage": percentage,
            "over": spent > limit,
        })

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
        category_budgets=category_budgets,
        search_term=search_term,
        type_filter=type_filter,
    )


# =========================
# MONTHLY HISTORY
# =========================

@app.route("/history")
@login_required
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

    # Chronological order (oldest first) for the line chart
    chart_months = list(reversed(months))

    return render_template(
        "history.html",
        months=months,
        max_value=max_value,
        chart_labels=[m["month"] for m in chart_months],
        chart_income=[m["income"] for m in chart_months],
        chart_expenses=[m["expenses"] for m in chart_months],
    )


# =========================
# EXPORT TO CSV
# =========================

@app.route("/export-csv")
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
# CATEGORY BUDGETS
# =========================

# Keep this in sync with the categories offered in add_expense.html
EXPENSE_CATEGORIES = [
    "Food", "Transport", "Rent", "Utilities",
    "Shopping", "Entertainment", "Health", "Other",
]


@app.route("/category-budgets", methods=["GET", "POST"])
@login_required
def category_budgets_view():

    today = date.today()
    current_month = today.strftime("%Y-%m")

    connection = get_db_connection()

    if request.method == "POST":

        for category in EXPENSE_CATEGORIES:
            field_name = f"amount_{category}"
            amount = request.form.get(field_name, "").strip()

            if amount and is_positive_number(amount):
                connection.execute("""
                    INSERT INTO category_budgets (month, category, amount)
                    VALUES (?, ?, ?)
                    ON CONFLICT(month, category)
                    DO UPDATE SET amount = excluded.amount
                """, (current_month, category, float(amount)))
            elif amount == "":
                # Empty field means "no budget for this category" - remove any existing one
                connection.execute("""
                    DELETE FROM category_budgets
                    WHERE month = ? AND category = ?
                """, (current_month, category))

        connection.commit()
        connection.close()

        flash("Category budgets updated.", "success")
        return redirect(url_for("home"))

    existing_rows = connection.execute("""
        SELECT category, amount
        FROM category_budgets
        WHERE month = ?
    """, (current_month,)).fetchall()

    connection.close()

    existing = {row["category"]: row["amount"] for row in existing_rows}

    return render_template(
        "category_budgets.html",
        categories=EXPENSE_CATEGORIES,
        existing=existing,
        month_name=today.strftime("%B %Y"),
    )


# =========================
# RECURRING TRANSACTIONS
# =========================

@app.route("/recurring")
@login_required
def recurring_list():

    connection = get_db_connection()

    items = connection.execute("""
        SELECT *
        FROM recurring_transactions
        ORDER BY active DESC, day_of_month ASC
    """).fetchall()

    connection.close()

    return render_template("recurring.html", items=items, today=date.today().isoformat())


@app.route("/recurring/add", methods=["POST"])
@login_required
def recurring_add():

    amount = request.form.get("amount", "").strip()
    transaction_type = request.form.get("type", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    payment_method = request.form.get("payment_method", "").strip()
    day_of_month = request.form.get("day_of_month", "").strip()

    if not is_positive_number(amount) or transaction_type not in ("income", "expense") or not category:
        flash("Please fill in a valid amount, type, and category.", "error")
        return redirect(url_for("recurring_list"))

    try:
        day_of_month_int = int(day_of_month)
        if not (1 <= day_of_month_int <= 28):
            raise ValueError
    except ValueError:
        flash("Day of month must be between 1 and 28 (to work in every month safely).", "error")
        return redirect(url_for("recurring_list"))

    connection = get_db_connection()

    connection.execute("""
        INSERT INTO recurring_transactions
        (amount, type, category, description, payment_method, day_of_month, active, last_added_month)
        VALUES (?, ?, ?, ?, ?, ?, 1, NULL)
    """, (
        float(amount), transaction_type, category,
        description, payment_method, day_of_month_int
    ))

    connection.commit()
    connection.close()

    flash("Recurring transaction added.", "success")
    return redirect(url_for("recurring_list"))


@app.route("/recurring/toggle/<int:recurring_id>", methods=["POST"])
@login_required
def recurring_toggle(recurring_id):

    connection = get_db_connection()

    connection.execute("""
        UPDATE recurring_transactions
        SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END
        WHERE id = ?
    """, (recurring_id,))

    connection.commit()
    connection.close()

    return redirect(url_for("recurring_list"))


@app.route("/recurring/delete/<int:recurring_id>", methods=["POST"])
@login_required
def recurring_delete(recurring_id):

    connection = get_db_connection()

    connection.execute("""
        DELETE FROM recurring_transactions
        WHERE id = ?
    """, (recurring_id,))

    connection.commit()
    connection.close()

    flash("Recurring transaction removed.", "success")
    return redirect(url_for("recurring_list"))


def apply_due_recurring_transactions(connection, today):
    """
    For every active recurring transaction whose day_of_month has passed (or
    is today) in the current month, and which hasn't already been added this
    month, insert a real transaction and mark it as added for this month.
    """
    current_month = today.strftime("%Y-%m")

    due_items = connection.execute("""
        SELECT *
        FROM recurring_transactions
        WHERE active = 1
        AND day_of_month <= ?
        AND (last_added_month IS NULL OR last_added_month != ?)
    """, (today.day, current_month)).fetchall()

    for item in due_items:
        transaction_date = f"{current_month}-{item['day_of_month']:02d}"

        connection.execute("""
            INSERT INTO transactions
            (amount, type, category, description, payment_method, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            item["amount"],
            item["type"],
            item["category"],
            item["description"],
            item["payment_method"],
            transaction_date,
        ))

        connection.execute("""
            UPDATE recurring_transactions
            SET last_added_month = ?
            WHERE id = ?
        """, (current_month, item["id"]))

    if due_items:
        connection.commit()


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
