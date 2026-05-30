import os
import sqlite3
from datetime import datetime
from typing import Iterable

from werkzeug.security import generate_password_hash

import setting

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(setting.BASE_DIR, "instance", "credit_scoring.db"),
)


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                position TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'analyst')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            );

            CREATE TABLE IF NOT EXISTS borrowers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                passport_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                borrower_id INTEGER NOT NULL,
                employee_id INTEGER,
                product_type TEXT NOT NULL,
                requested_amount REAL NOT NULL,
                approved_amount REAL NOT NULL,
                interest_rate REAL NOT NULL,
                risk_probability REAL NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected')),
                employment_status TEXT NOT NULL,
                decision_comment TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (borrower_id) REFERENCES borrowers(id),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            );

            CREATE TABLE IF NOT EXISTS application_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                feature_name TEXT NOT NULL,
                feature_label TEXT NOT NULL,
                value REAL NOT NULL,
                FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )
        seed_reference_data(conn)


def seed_reference_data(conn):
    departments = [
        ("RISK", "Отдел риск-аналитики", "Настройка скоринговой модели и контроль риск-метрик"),
        ("SALES", "Кредитный отдел", "Оформление заявок и коммуникация с заемщиками"),
        ("IT", "Отдел сопровождения ИС", "Поддержка веб-системы и базы данных"),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO departments (code, name, description)
        VALUES (?, ?, ?)
        """,
        departments,
    )

    employees = [
        ("RISK", "Анна Смирнова", "Риск-аналитик", "risk@credit-ai.local", "+7 343 100-10-01"),
        ("SALES", "Иван Петров", "Кредитный менеджер", "manager@credit-ai.local", "+7 343 100-10-02"),
        ("IT", "Мария Кузнецова", "Администратор системы", "admin@credit-ai.local", "+7 343 100-10-03"),
    ]
    for code, full_name, position, email, phone in employees:
        department_id = conn.execute(
            "SELECT id FROM departments WHERE code = ?", (code,)
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT OR IGNORE INTO employees
                (department_id, full_name, position, email, phone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (department_id, full_name, position, email, phone),
        )

    users = [
        ("admin", "admin123", "admin@credit-ai.local", "admin"),
        ("manager", "manager123", "manager@credit-ai.local", "manager"),
        ("analyst", "analyst123", "risk@credit-ai.local", "analyst"),
    ]
    for username, password, email, role in users:
        employee = conn.execute(
            "SELECT id FROM employees WHERE email = ?", (email,)
        ).fetchone()
        conn.execute(
            """
            INSERT OR IGNORE INTO users
                (employee_id, username, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (employee["id"], username, generate_password_hash(password), role),
        )


def upsert_borrower(form_data):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO borrowers (full_name, email, phone, passport_hash)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(passport_hash) DO UPDATE SET
                full_name = excluded.full_name,
                email = excluded.email,
                phone = excluded.phone
            """,
            (
                form_data["full_name"],
                form_data["email"],
                form_data["phone"],
                form_data["passport_hash"],
            ),
        )
        row = conn.execute(
            "SELECT id FROM borrowers WHERE passport_hash = ?",
            (form_data["passport_hash"],),
        ).fetchone()
        return row["id"]


def create_application(
    borrower_id: int,
    employee_id: int,
    form_data,
    prediction,
    offer,
    features: Iterable[tuple[str, str, float]],
    user_id: int | None = None,
):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO applications (
                borrower_id, employee_id, product_type, requested_amount,
                approved_amount, interest_rate, risk_probability, risk_level,
                status, employment_status, decision_comment, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                borrower_id,
                employee_id,
                form_data["product_type"],
                offer["requested_amount"],
                offer["amount"],
                offer["rate"],
                prediction["prob"],
                prediction["level"],
                offer["status"],
                form_data["employment_status"],
                offer["comment"],
                created_at,
            ),
        )
        application_id = cursor.lastrowid
        conn.executemany(
            """
            INSERT INTO application_features
                (application_id, feature_name, feature_label, value)
            VALUES (?, ?, ?, ?)
            """,
            [(application_id, name, label, value) for name, label, value in features],
        )
        conn.execute(
            """
            INSERT INTO audit_log (user_id, action, entity_type, entity_id)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, "create_application", "applications", application_id),
        )
        return application_id


def list_applications(limit=100, employee_id=None):
    with get_connection() as conn:
        where = ""
        params = []
        if employee_id:
            where = "WHERE a.employee_id = ?"
            params.append(employee_id)
        params.append(limit)
        return conn.execute(
            f"""
            SELECT
                a.*, b.full_name, b.email, b.phone,
                e.full_name AS employee_name
            FROM applications a
            JOIN borrowers b ON b.id = a.borrower_id
            LEFT JOIN employees e ON e.id = a.employee_id
            {where}
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()


def get_application(application_id):
    with get_connection() as conn:
        application = conn.execute(
            """
            SELECT a.*, b.full_name, b.email, b.phone, b.passport_hash,
                   e.full_name AS employee_name
            FROM applications a
            JOIN borrowers b ON b.id = a.borrower_id
            LEFT JOIN employees e ON e.id = a.employee_id
            WHERE a.id = ?
            """,
            (application_id,),
        ).fetchone()
        features = conn.execute(
            """
            SELECT feature_label, feature_name, value
            FROM application_features
            WHERE application_id = ?
            ORDER BY id
            """,
            (application_id,),
        ).fetchall()
        return application, features


def list_departments():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT d.*,
                   COUNT(e.id) AS employees_count
            FROM departments d
            LEFT JOIN employees e ON e.department_id = d.id
            GROUP BY d.id
            ORDER BY d.name
            """
        ).fetchall()


def list_employees():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT e.*, d.name AS department_name
            FROM employees e
            JOIN departments d ON d.id = e.department_id
            ORDER BY d.name, e.full_name
            """
        ).fetchall()


def list_users():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT u.*, e.full_name AS employee_name, d.name AS department_name
            FROM users u
            LEFT JOIN employees e ON e.id = u.employee_id
            LEFT JOIN departments d ON d.id = e.department_id
            ORDER BY u.role, u.username
            """
        ).fetchall()


def get_user_by_username(username):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT u.*, e.full_name AS employee_name, e.department_id,
                   e.position, d.name AS department_name
            FROM users u
            LEFT JOIN employees e ON e.id = u.employee_id
            LEFT JOIN departments d ON d.id = e.department_id
            WHERE u.username = ?
            """,
            (username,),
        ).fetchone()


def get_user_by_id(user_id):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT u.*, e.full_name AS employee_name, e.department_id,
                   e.position, e.email, d.name AS department_name
            FROM users u
            LEFT JOIN employees e ON e.id = u.employee_id
            LEFT JOIN departments d ON d.id = e.department_id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()


def create_employee_account(form_data):
    with get_connection() as conn:
        employee_cursor = conn.execute(
            """
            INSERT INTO employees
                (department_id, full_name, position, email, phone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                form_data["department_id"],
                form_data["full_name"],
                form_data["position"],
                form_data["email"],
                form_data.get("phone", ""),
            ),
        )
        employee_id = employee_cursor.lastrowid
        user_cursor = conn.execute(
            """
            INSERT INTO users (employee_id, username, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                employee_id,
                form_data["username"],
                generate_password_hash(form_data["password"]),
                form_data["role"],
            ),
        )
        return user_cursor.lastrowid


def get_default_employee_id():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM employees WHERE email = 'manager@credit-ai.local'"
        ).fetchone()
        return row["id"] if row else None


def get_dashboard_stats():
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS count FROM applications").fetchone()["count"]
        approved = conn.execute(
            "SELECT COUNT(*) AS count FROM applications WHERE status = 'approved'"
        ).fetchone()["count"]
        avg_pd = conn.execute(
            "SELECT AVG(risk_probability) AS value FROM applications"
        ).fetchone()["value"]
        employees = conn.execute("SELECT COUNT(*) AS count FROM employees").fetchone()["count"]
        return {
            "total_applications": total,
            "approved_applications": approved,
            "avg_pd": avg_pd or 0,
            "employees": employees,
        }
