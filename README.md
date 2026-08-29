# 💰 My Finances — Personal Finance Tracker

A Flask + SQLite web app for tracking income, expenses, and a monthly budget —
designed to run online so you can use it from both your phone and computer,
protected by a single username/password login.

## Features

- Add income and expenses with category, payment method, description, and date
- Edit or delete any transaction
- Monthly budget with a progress bar (% used and amount remaining)
- **Per-category budgets** with individual progress bars (e.g. Food: 5000, Transport: 2000)
- **Recurring transactions** — set rent, salary, subscriptions, etc. to auto-add each month
- Spending breakdown by category, shown as a pie chart and a list
- Search/filter transactions by keyword or type (income/expense)
- Monthly history with an income vs. expenses line chart, last 12 months
- Export all transactions to CSV
- Single username/password login (session-based, "remember me")
- Mobile-friendly layout, installable as a home-screen app (PWA)

---

## 1. Local setup

```bash
# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Create the database
python init_db.py

# Generate your login password hash
python generate_password_hash.py
```

`generate_password_hash.py` will ask you to type a password, then print a long
hash string like `scrypt:32768:8:1$...`. Copy it — you'll need it in the next step.

### Set your login credentials (required)

The app reads these from environment variables — never hardcode your password
in the code. On Windows PowerShell, for a local test run:

```powershell
$env:SECRET_KEY="some-long-random-string"
$env:APP_USERNAME="yourname"
$env:APP_PASSWORD_HASH="scrypt:32768:8:1$...(paste the full hash here)"
python app.py
```

Then open **http://127.0.0.1:5000** — you'll be asked to log in with the
username/password you just chose.

If you don't set `APP_PASSWORD_HASH`, login will always fail (this is intentional —
there's no default password).

---

## 2. Deploying so you can use it from your phone (PythonAnywhere)

PythonAnywhere's free tier is used here because, unlike some other free hosts,
your database file **won't get wiped** when you update your code — important
for a finance app.

1. **Create a free account** at https://www.pythonanywhere.com
2. **Upload your project**:
   - Easiest: push your code to GitHub (you're already doing this), then in
     PythonAnywhere open a **Bash console** and run:
     ```
     git clone https://github.com/jokacoded124/finance_tracker.git
     ```
3. **Create a virtualenv and install dependencies** (in the Bash console):
   ```
   cd finance_tracker
   python3.10 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python init_db.py
   python generate_password_hash.py
   ```
   Copy the printed hash for the next step.
4. **Set environment variables**: Go to the **Web** tab → your web app →
   scroll to **Environment variables** and add:
   - `SECRET_KEY` = a long random string
   - `APP_USERNAME` = your chosen username
   - `APP_PASSWORD_HASH` = the hash from step 3
5. **Configure the Web app** (Web tab):
   - Set the source code directory to `/home/yourusername/finance_tracker`
   - Set the working directory the same way
   - Edit the WSGI file it gives you so it points to your `app.py`'s `app` object, e.g.:
     ```python
     import sys
     path = '/home/yourusername/finance_tracker'
     if path not in sys.path:
         sys.path.append(path)
     from app import app as application
     ```
   - Point the virtualenv path to `/home/yourusername/finance_tracker/venv`
6. Click **Reload** on the Web tab. Your app is now live at
   `https://yourusername.pythonanywhere.com` — open that on your phone and
   your computer, log in, and you're tracking finances from anywhere.

### Updating the live app later

Whenever you make changes locally and push to GitHub, pull them on PythonAnywhere:
```
cd finance_tracker
git pull
```
Then hit **Reload** on the Web tab. Your `finance.db` stays untouched.

### If you're upgrading an existing live database (adding category budgets / recurring transactions)

If your `finance.db` already exists on the server from before these features were added,
run the migration script once, in a Bash console, instead of `init_db.py`:

```
cd finance_tracker
source venv/bin/activate
python migrate.py
```

This safely adds the two new tables without touching any of your existing transactions
or budgets. It's safe to run more than once. Then **Reload** the web app.

On PythonAnywhere's free tier there's no "Environment variables" section on the Web tab —
credentials are set directly inside the WSGI configuration file instead
(`/var/www/yourusername_pythonanywhere_com_wsgi.py`):

```python
import sys
import os

path = '/home/yourusername/finance_tracker'
if path not in sys.path:
    sys.path.append(path)

os.environ['SECRET_KEY'] = 'your-secret-key'
os.environ['APP_USERNAME'] = 'your-username'
os.environ['APP_PASSWORD_HASH'] = 'your-hash-from-generate_password_hash.py'

from app import app as application
```

---

## Project Structure

```
finance_tracker/
├── app.py                       # Flask routes and logic
├── database.py                  # Shared DB connection helper
├── init_db.py                   # Creates tables (run once)
├── generate_password_hash.py    # One-time helper to create your login hash
├── requirements.txt
├── .env.example                 # Reference for required environment variables
├── static/
│   └── css/style.css
└── templates/
    ├── login.html
    ├── dashboard.html
    ├── add_income.html
    ├── add_expense.html
    ├── edit_transaction.html
    ├── set_budget.html
    └── history.html
```

## Security notes

- `finance.db` is excluded from git via `.gitignore` — it holds your real data.
- Never commit `SECRET_KEY` or `APP_PASSWORD_HASH` to GitHub — always set them
  as environment variables on whatever host you use.
- `debug=True` in `app.py` is fine for local development but should be
  turned off (`debug=False`) for anything public-facing — PythonAnywhere
  handles this for you automatically since it doesn't use `app.run()` directly.

## Possible next steps

- Per-category budgets instead of one overall monthly budget
- Recurring transactions (rent, subscriptions)
- Charts via Chart.js instead of CSS bars
- "Add to Home Screen" support (PWA manifest) for a more app-like feel on mobile
