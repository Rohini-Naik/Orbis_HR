"""Operator CLI for tasks that must not be reachable over the network.

    python -m app.provision load-employees       # load the employee CSV
    python -m app.provision backfill-emails      # fill any missing company addresses
    python -m app.provision create-admin  --email hr.head@orbis.com
    python -m app.provision promote       --email someone@orbis.com
    python -m app.provision demote        --email someone@orbis.com
    python -m app.provision list-admins

Creating the first administrator is a bootstrap problem — granting admin rights
requires being an admin — so it is solved here, on the machine, rather than by
exposing a privileged endpoint.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import sys
from pathlib import Path
from typing import Optional

import mysql.connector

from app.auth import hash_password
from app.db import execute, query_all, query_one
from app.services.identity import generate_email
from rag_engine import settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMPLOYEE_CSV = PROJECT_ROOT / "database_data" / "employees.csv"
BATCH = 1000

# Columns whose empty CSV cells must become NULL rather than '' or a zero-date.
DATE_COLUMNS = {"DateOfJoining", "LastAppraisalDate", "NextAppraisalDate", "POSHTrainingDate"}
INT_COLUMNS = {
    "CasualLeaveBalance", "CasualLeaveUsed", "SickLeaveBalance", "SickLeaveUsed",
    "EarnedLeaveBalance", "EarnedLeaveUsed", "AnnualCTC_INR",
}


def _hr_conn():
    return mysql.connector.connect(**settings.get_hr_admin_mysql_config(), connection_timeout=20)


def load_employees(csv_path: Optional[Path] = None) -> None:
    """Load the employee CSV.

    Done here rather than with `LOAD DATA LOCAL INFILE`, which needs the SUPER
    privilege to enable, a matching client-side flag, and a path relative to the
    server's working directory — three things that differ across machines.
    """
    path = csv_path or EMPLOYEE_CSV
    if not path.exists():
        sys.exit(f"CSV not found: {path}")

    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        sys.exit(f"{path.name} has no rows")

    columns = [c for c in rows[0] if c]

    def coerce(column: str, value: str):
        value = (value or "").strip()
        if not value:
            return None
        if column in INT_COLUMNS:
            try:
                return int(value)
            except ValueError:
                return None
        return value

    conn = _hr_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM employees")
    existing = cur.fetchone()[0]
    if existing:
        print(f"Replacing {existing} existing row(s).")
        cur.execute("DELETE FROM employees")

    placeholders = ", ".join(["%s"] * len(columns))
    statement = f"INSERT INTO employees ({', '.join(columns)}) VALUES ({placeholders})"
    values = [tuple(coerce(c, row.get(c, "")) for c in columns) for row in rows]

    try:
        for start in range(0, len(values), BATCH):
            cur.executemany(statement, values[start:start + BATCH])
            conn.commit()
    except mysql.connector.Error as exc:
        conn.rollback()
        if exc.errno == 1054:
            sys.exit(
                f"Column mismatch: {exc.msg}\n"
                "The employees table does not match the CSV. Re-run:\n"
                "    sudo mysql < scripts/bootstrap_local_mysql.sql"
            )
        sys.exit(f"Load failed: {exc}")

    cur.execute("SELECT COUNT(*) FROM employees")
    print(f"Loaded {cur.fetchone()[0]} employees from {path.name}.")
    cur.close()
    conn.close()


# --------------------------------------------------------------------- emails
def backfill_emails() -> None:
    """Give every employee a unique company address. Idempotent: rows that
    already have one keep it, and their address is reserved so later rows do
    not collide with it."""
    conn = _hr_conn()
    cur = conn.cursor()
    cur.execute("SELECT EmployeeID, FullName, Email FROM employees ORDER BY EmployeeID")
    rows = cur.fetchall()

    taken = {email.lower() for _, _, email in rows if email}
    pending = []
    for emp_id, name, existing in rows:
        if existing:
            continue
        email = generate_email(name, is_taken=lambda e: e.lower() in taken)
        taken.add(email.lower())
        pending.append((email, emp_id))

    print(f"{len(rows)} employees · {len(rows) - len(pending)} already addressed · "
          f"{len(pending)} to mint")
    for start in range(0, len(pending), BATCH):
        chunk = pending[start:start + BATCH]
        cur.executemany("UPDATE employees SET Email = %s WHERE EmployeeID = %s", chunk)
        conn.commit()
        print(f"  {min(start + BATCH, len(pending))}/{len(pending)}")

    cur.execute("SELECT COUNT(*) FROM employees WHERE Email IS NOT NULL")
    print(f"Done. {cur.fetchone()[0]} employees now have a company address.")
    cur.close()
    conn.close()


# --------------------------------------------------------------------- admins
def _employee_by_email(email: str) -> Optional[dict]:
    conn = mysql.connector.connect(**settings.get_mysql_config(), connection_timeout=10)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT EmployeeID, FullName, Department, Status FROM employees WHERE Email = %s",
            (email,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def create_admin(email: str, full_name: Optional[str] = None) -> None:
    existing = query_one("SELECT id, role FROM users WHERE email = %s", (email,))
    if existing:
        if existing["role"] == "admin":
            print(f"{email} is already an administrator.")
            return
        execute("UPDATE users SET role = 'admin' WHERE id = %s", (existing["id"],))
        print(f"Promoted existing account {email} to administrator.")
        return

    record = _employee_by_email(email)
    if record is None:
        print(f"Warning: {email} does not match any employee record.")
        if input("Create the administrator anyway? [y/N] ").strip().lower() != "y":
            sys.exit("Aborted.")

    name = full_name or (record or {}).get("FullName") or email.split("@")[0]
    password = getpass.getpass(f"Choose a password for {email}: ")
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters.")
    if password != getpass.getpass("Confirm password: "):
        sys.exit("Passwords do not match.")

    execute(
        "INSERT INTO users (email, password_hash, full_name, role, employee_id, department) "
        "VALUES (%s, %s, %s, 'admin', %s, %s)",
        (email, hash_password(password), name,
         (record or {}).get("EmployeeID"), (record or {}).get("Department")),
    )
    print(f"Created administrator {email}.")


def set_role(email: str, role: str) -> None:
    user = query_one("SELECT id, role FROM users WHERE email = %s", (email,))
    if user is None:
        sys.exit(f"No account found for {email}.")
    if user["role"] == role:
        print(f"{email} is already '{role}'.")
        return
    if role != "admin":
        admins = query_one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")["n"]
        if admins <= 1:
            sys.exit("Refusing to demote the last administrator.")
    execute("UPDATE users SET role = %s WHERE id = %s", (role, user["id"]))
    print(f"{email} is now '{role}'.")


def list_admins() -> None:
    admins = query_all(
        "SELECT email, full_name, employee_id, created_at FROM users "
        "WHERE role = 'admin' ORDER BY id"
    )
    if not admins:
        print("No administrators exist. Create one with: "
              "python -m app.provision create-admin --email you@company.com")
        return
    for a in admins:
        print(f"  {a['email']:36} {a['full_name']:26} emp={a['employee_id']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.provision")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("backfill-emails", help="mint company addresses for all employees")
    sub.add_parser("list-admins", help="show current administrators")

    load = sub.add_parser("load-employees", help="load database_data/employees.csv")
    load.add_argument("--csv", type=Path)

    create = sub.add_parser("create-admin", help="create or promote an administrator")
    create.add_argument("--email", required=True)
    create.add_argument("--name")

    for name in ("promote", "demote"):
        p = sub.add_parser(name, help=f"{name} an existing account")
        p.add_argument("--email", required=True)

    args = parser.parse_args()

    # The CLI is often the first thing to touch a freshly created database,
    # so make sure the application's tables exist before querying them.
    from app.db import init_db
    init_db()

    if args.command == "load-employees":
        load_employees(args.csv)
    elif args.command == "backfill-emails":
        backfill_emails()
    elif args.command == "create-admin":
        create_admin(args.email, args.name)
    elif args.command == "promote":
        set_role(args.email, "admin")
    elif args.command == "demote":
        set_role(args.email, "employee")
    elif args.command == "list-admins":
        list_admins()


if __name__ == "__main__":
    main()
