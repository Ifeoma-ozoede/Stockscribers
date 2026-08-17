#!/usr/bin/env python3
"""
Change a Stockscribes password (or add a new person).

Use this before sharing the site with anyone outside your own screen —
the sample passwords are only meant for testing.

Run it:   python3 set_password.py
"""

import getpass
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("STOCKSCRIBES_DB") or os.path.join(HERE, "stockscribes.db")

sys.path.insert(0, HERE)
from server import hash_password  # reuses the same secure hashing as the website


def main():
    if not os.path.exists(DB_PATH):
        print("\n  No database found yet. Start the website once (python3 server.py) first.\n")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    people = conn.execute(
        "SELECT u.id, u.email, u.display_name, u.role, s.name supplier"
        " FROM users u LEFT JOIN suppliers s ON s.id = u.supplier_id ORDER BY u.id").fetchall()

    print("\n  People who can sign in:\n")
    for i, p in enumerate(people, 1):
        who = p["supplier"] or "Stockscribes Pharmacy"
        print(f"    {i}. {p['email']}  —  {who} ({p['role']})")
    print()

    choice = input("  Number of the person to change (or Enter to cancel): ").strip()
    if not choice:
        print("  Cancelled.\n")
        return
    try:
        person = people[int(choice) - 1]
    except (ValueError, IndexError):
        print("  That wasn't one of the numbers.\n")
        return

    print(f"\n  Changing the password for {person['email']}")
    pw1 = getpass.getpass("  New password (typing stays hidden): ")
    if len(pw1) < 8:
        print("\n  Too short — please use at least 8 characters.\n")
        return
    pw2 = getpass.getpass("  Type it again to confirm: ")
    if pw1 != pw2:
        print("\n  Those didn't match. Nothing was changed.\n")
        return

    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(pw1), person["id"]))
    conn.commit()
    conn.close()
    print(f"\n  Done. {person['email']} now signs in with the new password.\n")


if __name__ == "__main__":
    main()
