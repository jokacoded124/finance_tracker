# 💰 My Finances — Personal Finance Tracker

A simple Flask + SQLite web app for tracking income, expenses, and a monthly budget.

## Features

- Add income and expenses with category, payment method, description, and date
- Edit or delete any transaction
- Monthly budget with a progress bar (shows % used and amount remaining)
- Spending breakdown by category for the current month
- Search/filter transactions by keyword or type (income/expense)
- Monthly history view comparing income vs. expenses over the last 12 months
- Export all transactions to CSV
- Input validation and flash messages for errors/success

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize the database (creates finance.db)
python init_db.py

# 4. Run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Project Structure

```
finance_tracker/
├── app.py                  # Flask routes and logic
├── database.py             # Shared DB connection helper
├── init_db.py               # Creates tables (run once)
├── requirements.txt
├── static/
│   └── css/style.css
└── templates/
    ├── dashboard.html
    ├── add_income.html
    ├── add_expense.html
    ├── edit_transaction.html
    ├── set_budget.html
    └── history.html
```

## Notes

- `finance.db` is excluded from git via `.gitignore` since it contains your personal data.
- Change `app.secret_key` in `app.py` before deploying anywhere public.
- Set `debug=False` in `app.run()` before deploying to production.

## Possible next steps

- User accounts / authentication (multiple users, one DB)
- Recurring transactions (e.g. rent, subscriptions)
- Per-category budgets, not just one overall monthly budget
- Charts using Chart.js instead of CSS bars
- Deploy to Render/Railway/PythonAnywhere
