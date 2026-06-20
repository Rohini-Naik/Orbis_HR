"""Admin employee management — create/list/update/delete rows in the HR
`employees` table via a dedicated read-write connection. The NL->SQL engine
keeps using the read-only user, so this write access never reaches the LLM path.
"""
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

import mysql.connector
from fastapi import HTTPException, status

from app.services import audit_service
from rag_engine import settings

COLUMNS = [
    "EmployeeID", "EmployeeName", "Age", "Gender", "Location", "Department",
    "Role", "YearsAtCompany", "DateOfJoining", "YearsInCurrentRole",
    "EducationLevel", "MonthlySalaryINR", "WorkHoursPerWeek", "ProjectsHandled",
    "TrainingHoursLastYear", "SickLeavesLastYear", "OvertimeHoursLastMonth",
    "ManagerRating", "DisciplinaryNotices", "PolicyViolationsLastYear",
    "PerformanceRating", "PromotionLast2Years", "ComplianceRiskLevel",
    "AttritionRisk",
]


@contextmanager
def _conn() -> Iterator[mysql.connector.MySQLConnection]:
    conn = mysql.connector.connect(**settings.get_hr_admin_mysql_config(), connection_timeout=10)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create(data: Dict[str, Any], admin: Dict[str, Any]) -> Dict[str, Any]:
    cols = [c for c in COLUMNS if c in data]
    placeholders = ", ".join(["%s"] * len(cols))
    values = [data[c] for c in cols]
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM employees WHERE EmployeeID = %s", (data["EmployeeID"],))
        if cur.fetchone():
            raise HTTPException(status.HTTP_409_CONFLICT, "EmployeeID already exists")
        try:
            cur.execute(
                f"INSERT INTO employees ({', '.join(cols)}) VALUES ({placeholders})", values
            )
        except mysql.connector.Error as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        cur.close()
    audit_service.log_event("employee", user=admin, question=f"Added employee {data['EmployeeID']}")
    return get(data["EmployeeID"])


def list_employees(search: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    where, params = "", []
    if search:
        where = "WHERE EmployeeName LIKE %s OR Department LIKE %s OR Role LIKE %s"
        params = [f"%{search}%"] * 3
    with _conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(f"SELECT COUNT(*) AS n FROM employees {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"SELECT * FROM employees {where} ORDER BY EmployeeID LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        rows = cur.fetchall()
        cur.close()
    return {"total": total, "employees": rows}


def get(employee_id: int) -> Dict[str, Any]:
    with _conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM employees WHERE EmployeeID = %s", (employee_id,))
        row = cur.fetchone()
        cur.close()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    return row


def update(employee_id: int, data: Dict[str, Any], admin: Dict[str, Any]) -> Dict[str, Any]:
    fields = [c for c in COLUMNS if c in data and c != "EmployeeID"]
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    assignments = ", ".join(f"{c} = %s" for c in fields)
    values = [data[c] for c in fields] + [employee_id]
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE employees SET {assignments} WHERE EmployeeID = %s", values)
        affected = cur.rowcount
        cur.close()
    if affected == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    audit_service.log_event("employee", user=admin, question=f"Updated employee {employee_id}")
    return get(employee_id)


def delete(employee_id: int, admin: Dict[str, Any]) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM employees WHERE EmployeeID = %s", (employee_id,))
        affected = cur.rowcount
        cur.close()
    if affected == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    audit_service.log_event("employee", user=admin, question=f"Deleted employee {employee_id}")
