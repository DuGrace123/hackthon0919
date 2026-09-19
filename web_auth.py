from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
ROLES = {"admin", "editor"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_username(value: object) -> str:
    username = str(value or "").strip()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("用户名须为 3–32 位，只能包含字母、数字、点、下划线或连字符")
    return username


def validate_password(value: object) -> str:
    password = str(value or "")
    if len(password) < 8 or len(password) > 128:
        raise ValueError("密码长度须为 8–128 个字符")
    return password


def validate_role(value: object) -> str:
    role = str(value or "editor").strip().lower()
    if role not in ROLES:
        raise ValueError("账户角色必须是 admin 或 editor")
    return role


class AccountStore:
    """Small SQLite-backed account store used by the local web editor."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'editor')),
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                )
                """
            )

    @staticmethod
    def public(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_login_at": row["last_login_at"],
        }

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def active_admin_count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
                ).fetchone()[0]
            )

    def get(self, user_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def get_by_username(self, username: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    def list(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END, username COLLATE NOCASE"
            ).fetchall()
        return [self.public(row) for row in rows]

    def create(self, username: str, password_hash: str, role: str = "editor") -> dict:
        username = validate_username(username)
        role = validate_role(role)
        now = utc_now()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash, role, is_active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                    (username, password_hash, role, now, now),
                )
                row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValueError("该用户名已存在") from exc
        return self.public(row)

    def update(self, user_id: int, *, role=None, is_active=None, password_hash=None) -> dict:
        row = self.get(user_id)
        if row is None:
            raise ValueError("找不到该账户")
        assignments: list[str] = []
        values: list[object] = []
        if role is not None:
            assignments.append("role = ?")
            values.append(validate_role(role))
        if is_active is not None:
            assignments.append("is_active = ?")
            values.append(1 if bool(is_active) else 0)
        if password_hash is not None:
            assignments.append("password_hash = ?")
            values.append(password_hash)
        if assignments:
            assignments.append("updated_at = ?")
            values.append(utc_now())
            values.append(user_id)
            with self._connect() as connection:
                connection.execute(f"UPDATE users SET {', '.join(assignments)} WHERE id = ?", values)
        return self.public(self.get(user_id))

    def delete(self, user_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            if not cursor.rowcount:
                raise ValueError("找不到该账户")

    def touch_login(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (utc_now(), utc_now(), user_id),
            )
