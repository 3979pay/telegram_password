import sqlite3
from datetime import datetime

from config import DATABASE_PATH


def init_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS last_accounts (
                user_id INTEGER PRIMARY KEY,
                account TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_passwords (
                user_id INTEGER PRIMARY KEY,
                request_type TEXT NOT NULL,
                account TEXT NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_requests (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                processed_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, message_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                group_name TEXT,
                group_id INTEGER,
                confirmer_id INTEGER,
                confirmer_name TEXT,
                recipient_id INTEGER,
                recipient_name TEXT,
                request_type TEXT,
                account TEXT,
                password TEXT
            )
            """
        )


def save_last_account(user_id: int, account: str) -> None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO last_accounts (user_id, account)
            VALUES (?, ?)
            """,
            (user_id, account),
        )


def get_last_account(user_id: int) -> str | None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        row = conn.execute(
            "SELECT account FROM last_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row[0] if row else None


def save_pending_password(
    user_id: int,
    request_type: str,
    account: str,
    password: str,
) -> None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO pending_passwords
            (user_id, request_type, account, password)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, request_type, account, password),
        )


def get_pending_password(user_id: int):
    with sqlite3.connect(DATABASE_PATH) as conn:
        return conn.execute(
            """
            SELECT request_type, account, password
            FROM pending_passwords
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()


def delete_pending_password(user_id: int) -> None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "DELETE FROM pending_passwords WHERE user_id = ?",
            (user_id,),
        )


def is_processed(chat_id: int, message_id: int) -> bool:
    with sqlite3.connect(DATABASE_PATH) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM processed_requests
            WHERE chat_id = ? AND message_id = ?
            """,
            (chat_id, message_id),
        ).fetchone()
    return row is not None


def mark_processed(chat_id: int, message_id: int) -> None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO processed_requests
            (chat_id, message_id, processed_at)
            VALUES (?, ?, ?)
            """,
            (
                chat_id,
                message_id,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def save_history(
    *,
    group_name: str,
    group_id: int,
    confirmer_id: int,
    confirmer_name: str,
    recipient_id: int,
    recipient_name: str,
    request_type: str,
    account: str,
    password: str,
) -> None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            INSERT INTO history (
                created_at,
                group_name,
                group_id,
                confirmer_id,
                confirmer_name,
                recipient_id,
                recipient_name,
                request_type,
                account,
                password
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                group_name,
                group_id,
                confirmer_id,
                confirmer_name,
                recipient_id,
                recipient_name,
                request_type,
                account,
                password,
            ),
        )
