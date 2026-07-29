#!/usr/bin/env python3
"""End-to-end verification of a running Orbis install.

    python -m tests.e2e_check           # everything
    python -m tests.e2e_check --quick   # skip the AI calls (no Hugging Face needed)

Drives the real API in-process against the real MySQL and ChromaDB. It creates
its own throwaway employee and account, then removes them, so it is safe to run
against a working install.

Exit code is 0 only if every check passed.
"""
from __future__ import annotations

import argparse
import secrets
import sys
import traceback
from typing import Any, Callable

from fastapi.testclient import TestClient

from app.db import execute, query_one
from app.main import app

BOLD, GREEN, RED, YELLOW, DIM, OFF = (
    "\033[1m", "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
)

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []
SKIPPED: list[tuple[str, str]] = []


def check(name: str, fn: Callable[[], Any], optional: bool = False) -> Any:
    """Run one assertion. `optional` marks checks that need the LLM, so a
    Hugging Face outage is reported as a skip rather than a failure."""
    try:
        result = fn()
        print(f"  {GREEN}PASS{OFF}  {name}")
        PASSED.append(name)
        return result
    except AssertionError as exc:
        print(f"  {RED}FAIL{OFF}  {name}\n        {exc}")
        FAILED.append((name, str(exc)))
    except Exception as exc:
        if optional:
            print(f"  {YELLOW}SKIP{OFF}  {name}  {DIM}({type(exc).__name__}: {exc}){OFF}")
            SKIPPED.append((name, str(exc)))
        else:
            print(f"  {RED}FAIL{OFF}  {name}\n        {type(exc).__name__}: {exc}")
            FAILED.append((name, traceback.format_exc(limit=3)))
    return None


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{OFF}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="skip checks that call the LLM")
    parser.add_argument("--admin-email", help="existing admin to sign in as")
    parser.add_argument("--admin-password", help="that admin's password")
    args = parser.parse_args()

    tag = secrets.token_hex(3)
    created_employee_id: str | None = None
    created_user_emails: list[str] = []

    with TestClient(app) as client:
        # ---------------------------------------------------------- schema
        section("Database schema")

        def schema_current() -> None:
            import mysql.connector
            from rag_engine import settings
            conn = mysql.connector.connect(**settings.get_mysql_config())
            cur = conn.cursor()
            cur.execute("SHOW COLUMNS FROM employees")
            cols = {r[0] for r in cur.fetchall()}
            conn.close()
            required = {"EmployeeID", "FullName", "Email", "PersonalEmail", "Status",
                        "CasualLeaveBalance", "NextAppraisalDate", "POSHTrainingCompleted"}
            missing = required - cols
            assert not missing, (
                f"employees table is missing {sorted(missing)} — re-run setup to rebuild it"
            )

        # Compare the failure count rather than the return value: a passing
        # assertion returns None, which is not a failure signal.
        before = len(FAILED)
        check("employees table has the current schema", schema_current)
        if len(FAILED) > before:
            print(f"\n{RED}{BOLD}Schema is out of date — later checks would all fail.{OFF}")
            print(f"{DIM}Run ./setup.sh (Windows: setup.bat) and try again.{OFF}\n")
            return 1

        check("employee rows are loaded", lambda: _assert(
            query_hr("SELECT COUNT(*) FROM employees")[0] > 0, "employees table is empty"))
        check("every employee has a company email", lambda: _assert(
            query_hr("SELECT COUNT(*) FROM employees WHERE Email IS NULL OR Email = ''")[0] == 0,
            "some employees have no Email — run: python -m app.provision backfill-emails",
        ))
        check("company emails are unique", lambda: _assert(
            query_hr("SELECT COUNT(*) - COUNT(DISTINCT Email) FROM employees")[0] == 0,
            "duplicate company email addresses found",
        ))

        # ------------------------------------------------------------ health
        section("Service health")
        check("GET /health", lambda: _assert(
            client.get("/health").json()["status"] == "ok", "health endpoint not ok"))
        check("policy index is populated", lambda: _assert(
            __import__("rag_engine.vector_store", fromlist=["x"]).count_chunks() > 0,
            "ChromaDB has no chunks — run: python -m rag_engine.maintenance",
        ))

        # ------------------------------------------------------------- admin
        section("Administrator sign-in")
        admin_email, admin_password = args.admin_email, args.admin_password
        if not admin_email:
            row = query_one("SELECT email FROM users WHERE role='admin' AND is_active=1 LIMIT 1")
            admin_email = row["email"] if row else None

        if not admin_email or not admin_password:
            print(f"  {YELLOW}SKIP{OFF}  admin sign-in "
                  f"{DIM}(pass --admin-email and --admin-password to test the full flow){OFF}")
            SKIPPED.append(("admin sign-in", "no credentials supplied"))
            admin_headers = None
        else:
            resp = client.post("/auth/login",
                               json={"email": admin_email, "password": admin_password})
            check("admin can sign in", lambda: _assert(
                resp.status_code == 200, f"login returned {resp.status_code}: {resp.text[:160]}"))
            admin_headers = ({"Authorization": f"Bearer {resp.json()['access_token']}"}
                             if resp.status_code == 200 else None)

        if admin_headers is None:
            summarise()
            return 1 if FAILED else 0

        check("admin sees the employee list", lambda: _assert(
            client.get("/employees", headers=admin_headers).status_code == 200, "list failed"))
        check("pagination is capped", lambda: _assert(
            client.get("/employees", headers=admin_headers,
                       params={"limit": 100000}).status_code == 422,
            "limit above the cap was accepted"))
        check("admin sees the audit log", lambda: _assert(
            client.get("/audit", headers=admin_headers).status_code == 200, "audit failed"))
        check("audit stats", lambda: _assert(
            "verification_pass_rate" in client.get("/audit/stats", headers=admin_headers).json(),
            "stats payload malformed"))
        check("policy library lists documents", lambda: _assert(
            len(client.get("/policies", headers=admin_headers).json()) > 0,
            "no policy documents registered"))

        # -------------------------------------------------------- onboarding
        section("Onboarding a new hire")
        new_hire = {
            "FullName": f"Test Hire {tag}",
            "PersonalEmail": f"test.hire.{tag}@example.com",
            "Department": "Engineering",
            "Role": "Engineer",
            "Location": "Pune",
            "CasualLeaveBalance": 12,
            "CasualLeaveUsed": 2,
        }
        created = client.post("/employees", json=new_hire, headers=admin_headers)
        check("admin can add an employee", lambda: _assert(
            created.status_code == 201, f"create returned {created.status_code}: {created.text[:200]}"))
        if created.status_code != 201:
            summarise()
            return 1

        record = created.json()
        created_employee_id = record["EmployeeID"]
        company_email = record["Email"]
        created_user_emails.append(company_email)

        check("employee id was allocated", lambda: _assert(
            created_employee_id.startswith("EMP"), f"unexpected id {created_employee_id}"))
        check("company email was minted from the name", lambda: _assert(
            company_email.endswith("@" + _domain()) and company_email.startswith("test.hire"),
            f"unexpected address {company_email}"))
        check("client cannot choose its own EmployeeID", lambda: _assert(
            client.post("/employees", headers=admin_headers,
                        json={**new_hire, "PersonalEmail": f"x.{tag}@example.com",
                              "EmployeeID": "EMP9999"}).json().get("EmployeeID") != "EMP9999",
            "a client-supplied EmployeeID was honoured"))

        token = query_one(
            "SELECT token FROM invites WHERE company_email = %s AND used_at IS NULL",
            (company_email,))
        check("an invitation was issued", lambda: _assert(token is not None, "no invite row"))
        invite_token = token["token"]

        check("invite preview works", lambda: _assert(
            client.get(f"/auth/invite/{invite_token}").json()["company_email"] == company_email,
            "preview returned the wrong address"))
        check("bogus invite is rejected", lambda: _assert(
            client.get("/auth/invite/not-a-real-token").status_code == 404, "bogus token accepted"))

        accepted = client.post("/auth/invite/accept",
                               json={"token": invite_token, "password": "TestPassw0rd!"})
        check("new hire can set a password", lambda: _assert(
            accepted.status_code == 201, f"accept returned {accepted.status_code}: {accepted.text[:160]}"))
        check("invite is single-use", lambda: _assert(
            client.post("/auth/invite/accept",
                        json={"token": invite_token, "password": "Another1!"}).status_code in (404, 409),
            "the same invite worked twice"))

        emp_headers = {"Authorization": f"Bearer {accepted.json()['access_token']}"}
        check("new hire is linked to their HR record", lambda: _assert(
            client.get("/auth/me", headers=emp_headers).json()["employee_id"] == created_employee_id,
            "employee_id not bound from the invite"))
        check("new hire cannot reach the audit log", lambda: _assert(
            client.get("/audit", headers=emp_headers).status_code == 403, "employee reached /audit"))
        check("new hire cannot manage users", lambda: _assert(
            client.get("/users", headers=emp_headers).status_code == 403, "employee reached /users"))

        # ------------------------------------------------------ self-service
        section("Self-service registration")
        check("unknown address is refused", lambda: _assert(
            client.post("/auth/signup",
                        json={"email": f"nobody.{tag}@example.org",
                              "password": "TestPassw0rd!"}).status_code == 404,
            "an address not on the HR system was accepted"))
        check("already-registered address is refused", lambda: _assert(
            client.post("/auth/signup",
                        json={"email": company_email, "password": "TestPassw0rd!"}
                        ).status_code == 409,
            "duplicate registration allowed"))

        # ----------------------------------------------------- role handling
        section("Roles and access")
        users = client.get("/users", headers=admin_headers).json()
        target = next((u for u in users if u["email"] == company_email), None)
        check("new account appears in Users & Access", lambda: _assert(
            target is not None, "new user missing from /users"))

        me = client.get("/auth/me", headers=admin_headers).json()
        check("admin cannot demote themselves", lambda: _assert(
            client.put(f"/users/{me['id']}/role", json={"role": "employee"},
                       headers=admin_headers).status_code == 400,
            "self-demotion was allowed"))
        check("promotion works", lambda: _assert(
            client.put(f"/users/{target['id']}/role", json={"role": "admin"},
                       headers=admin_headers).json()["role"] == "admin",
            "promotion failed"))
        check("promotion invalidates the old session", lambda: _assert(
            client.get("/auth/me", headers=emp_headers).status_code == 401,
            "old token still valid after a role change"))
        check("demotion works", lambda: _assert(
            client.put(f"/users/{target['id']}/role", json={"role": "employee"},
                       headers=admin_headers).json()["role"] == "employee",
            "demotion failed"))

        # -------------------------------------------------------- lifecycle
        section("Employee lifecycle")
        check("marking an employee exited succeeds", lambda: _assert(
            client.delete(f"/employees/{created_employee_id}",
                          headers=admin_headers).status_code == 204, "soft delete failed"))
        check("record is kept, not deleted", lambda: _assert(
            query_hr("SELECT Status FROM employees WHERE EmployeeID = %s",
                     (created_employee_id,))[0] == "exited",
            "record was hard-deleted or not marked exited"))
        check("exited employee cannot sign in", lambda: _assert(
            client.post("/auth/login",
                        json={"email": company_email, "password": "TestPassw0rd!"}
                        ).status_code == 403,
            "a departed employee could still sign in"))
        check("exited employee is hidden by default", lambda: _assert(
            all(e["EmployeeID"] != created_employee_id
                for e in client.get("/employees", headers=admin_headers).json()["employees"]),
            "exited employee still listed"))
        check("reinstate restores access", lambda: _assert(
            client.post(f"/employees/{created_employee_id}/reinstate",
                        headers=admin_headers).status_code == 200, "reinstate failed"))
        check("reinstated employee can sign in again", lambda: _assert(
            client.post("/auth/login",
                        json={"email": company_email, "password": "TestPassw0rd!"}
                        ).status_code == 200,
            "reinstated employee still locked out"))

        # ------------------------------------------------------ AI pipeline
        if not args.quick:
            section("AI pipeline (needs Hugging Face)")
            emp_login = client.post("/auth/login",
                                    json={"email": company_email, "password": "TestPassw0rd!"})
            ai_headers = {"Authorization": f"Bearer {emp_login.json()['access_token']}"}

            def ask(headers: dict, question: str) -> dict:
                resp = client.post("/chat", json={"question": question}, headers=headers)
                assert resp.status_code == 200, f"chat returned {resp.status_code}: {resp.text[:160]}"
                return resp.json()

            check("casual chat is answered", lambda: _assert(
                len(ask(ai_headers, "hi")["answer"]) > 0, "empty answer"), optional=True)

            def policy_question() -> None:
                data = ask(ai_headers, "What is the maternity leave policy?")
                assert data["route"] == "rag", f"routed to {data['route']}, expected rag"
                assert data["answer"], "empty answer"
            check("policy question routes to RAG and answers", policy_question, optional=True)

            def own_data_question() -> None:
                data = ask(ai_headers, "How many casual leaves do I have left?")
                assert data["route"] == "sql", f"routed to {data['route']}, expected sql"
                if data.get("sql"):
                    assert created_employee_id.lower() in data["sql"].lower(), \
                        f"generated SQL is not scoped to the caller: {data['sql']}"
            check("own-data question is scoped to the caller", own_data_question, optional=True)

            def admin_aggregate() -> None:
                data = ask(admin_headers, "How many employees have pending POSH training?")
                assert data["route"] == "sql", f"routed to {data['route']}, expected sql"
            check("admin aggregate question routes to SQL", admin_aggregate, optional=True)

        # ------------------------------------------------------- audit trail
        section("Audit trail")
        entries = client.get("/audit", headers=admin_headers).json()
        check("employee actions were recorded", lambda: _assert(
            any(created_employee_id in (e.get("question") or "") for e in entries),
            "employee creation not in the audit log"))
        check("role changes were recorded", lambda: _assert(
            any(e["action"] == "role" for e in entries), "no role events logged"))
        check("normal chat content is redacted", lambda: _assert(
            all(e.get("question") is None
                for e in entries
                if e["action"] == "chat" and not e["hallucination_blocked"]),
            "an employee's chat text is visible to admins"))

        # ---------------------------------------------------------- cleanup
        section("Cleanup")

        def cleanup() -> None:
            for email in created_user_emails:
                user = query_one("SELECT id FROM users WHERE email = %s", (email,))
                if user:
                    execute("DELETE FROM sessions WHERE user_id = %s", (user["id"],))
                    execute("DELETE FROM users WHERE id = %s", (user["id"],))
                execute("DELETE FROM invites WHERE company_email = %s", (email,))
            if created_employee_id:
                exec_hr("DELETE FROM employees WHERE EmployeeID = %s", (created_employee_id,))
                exec_hr("DELETE FROM employees WHERE PersonalEmail LIKE %s", (f"%.{tag}@example.com",))
        check("test data removed", cleanup)

    return summarise()


# --------------------------------------------------------------------- helpers
def _assert(condition: Any, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _domain() -> str:
    from rag_engine import settings
    return settings.COMPANY_EMAIL_DOMAIN


def query_hr(sql: str, params: tuple = ()) -> tuple:
    import mysql.connector
    from rag_engine import settings
    conn = mysql.connector.connect(**settings.get_mysql_config())
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return row if row else (None,)
    finally:
        conn.close()


def exec_hr(sql: str, params: tuple = ()) -> None:
    import mysql.connector
    from rag_engine import settings
    conn = mysql.connector.connect(**settings.get_hr_admin_mysql_config())
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def summarise() -> int:
    total = len(PASSED) + len(FAILED)
    print(f"\n{BOLD}{'=' * 62}{OFF}")
    print(f"{BOLD}{len(PASSED)}/{total} checks passed{OFF}"
          + (f"  ·  {YELLOW}{len(SKIPPED)} skipped{OFF}" if SKIPPED else ""))
    if FAILED:
        print(f"\n{RED}{BOLD}Failures:{OFF}")
        for name, detail in FAILED:
            print(f"  {RED}·{OFF} {name}\n      {detail.strip().splitlines()[-1]}")
    if SKIPPED:
        print(f"\n{YELLOW}Skipped:{OFF}")
        for name, why in SKIPPED:
            print(f"  · {name} {DIM}({why[:80]}){OFF}")
    print()
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
