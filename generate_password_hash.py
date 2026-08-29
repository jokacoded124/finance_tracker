"""
Run this once to generate a password hash for your login.

    python generate_password_hash.py

It will ask you to type a password, then print an APP_PASSWORD_HASH
value. Copy that into your environment variables (see README.md).
"""

import getpass
from werkzeug.security import generate_password_hash

password = getpass.getpass("Choose a password: ")
confirm = getpass.getpass("Confirm password: ")

if password != confirm:
    print("Passwords did not match. Please run this again.")
else:
    print("\nYour password hash (copy this entire value):\n")
    print(generate_password_hash(password))
    print("\nSet this as the APP_PASSWORD_HASH environment variable.")
