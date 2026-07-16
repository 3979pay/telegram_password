import sqlite3
from datetime import datetime

from config import DATABASE_PATH


def init_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            'CREATE TABLE IF NOT EXISTS last_accounts '
            '(user_id INTEGER PRIMARY KEY, account TEXT NOT NULL)'
        )
        conn.execute(
            'CREATE TABLE IF NOT EXISTS pending_requests '
            '(user_id INTEGER PRIMARY KEY, request_type TEXT NOT NULL, '
            'account TEXT NOT NULL, source_chat_id INTEGER NOT NULL, '
            'source_message_id INTEGER NOT NULL, updated_at TEXT NOT NULL)'
        )
        conn.execute(
            'CREATE TABLE IF NOT EXISTS pending_passwords '
            '(user_id INTEGER PRIMARY KEY, request_type TEXT NOT NULL, '
            'account TEXT NOT NULL, password TEXT NOT NULL)'
        )
        conn.execute(
            'CREATE TABLE IF NOT EXISTS processed_requests '
            '(chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, '
            'processed_at TEXT NOT NULL, PRIMARY KEY (chat_id, message_id))'
        )

        # Giữ tương thích với database cũ. Cột password cũ có thể vẫn tồn tại,
        # nhưng code mới sẽ không ghi mật khẩu vào bảng history.
        conn.execute(
            'CREATE TABLE IF NOT EXISTS history '
            '(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, '
            'group_name TEXT, group_id INTEGER, confirmer_id INTEGER, '
            'confirmer_name TEXT, recipient_id INTEGER, recipient_name TEXT, '
            'request_type TEXT, account TEXT, password TEXT)'
        )


def cleanup_old_data():
    """Dọn dữ liệu cũ khi bot khởi động."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        deleted_history = conn.execute(
            """
            DELETE FROM history
            WHERE datetime(created_at) < datetime('now', '-7 days')
            """
        ).rowcount

        deleted_processed = conn.execute(
            """
            DELETE FROM processed_requests
            WHERE datetime(processed_at) < datetime('now', '-7 days')
            """
        ).rowcount

        deleted_pending = conn.execute(
            """
            DELETE FROM pending_requests
            WHERE datetime(updated_at) < datetime('now', '-1 day')
            """
        ).rowcount

    return {
        "history": deleted_history,
        "processed": deleted_processed,
        "pending": deleted_pending,
    }


def save_last_account(user_id, account):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            'INSERT OR REPLACE INTO last_accounts (user_id, account) VALUES (?, ?)',
            (user_id, account),
        )


def get_last_account(user_id):
    with sqlite3.connect(DATABASE_PATH) as conn:
        row = conn.execute(
            'SELECT account FROM last_accounts WHERE user_id = ?',
            (user_id,),
        ).fetchone()
    return row[0] if row else None


def save_pending_request(user_id, request_type, account, source_chat_id, source_message_id):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            'INSERT OR REPLACE INTO pending_requests '
            '(user_id, request_type, account, source_chat_id, source_message_id, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (
                user_id,
                request_type,
                account,
                source_chat_id,
                source_message_id,
                datetime.now().isoformat(timespec='seconds'),
            ),
        )


def get_pending_request(user_id):
    with sqlite3.connect(DATABASE_PATH) as conn:
        return conn.execute(
            'SELECT request_type, account, source_chat_id, source_message_id '
            'FROM pending_requests WHERE user_id = ?',
            (user_id,),
        ).fetchone()


def delete_pending_request(user_id):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            'DELETE FROM pending_requests WHERE user_id = ?',
            (user_id,),
        )


def save_pending_password(user_id, request_type, account, password):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            'INSERT OR REPLACE INTO pending_passwords '
            '(user_id, request_type, account, password) VALUES (?, ?, ?, ?)',
            (user_id, request_type, account, password),
        )


def get_pending_password(user_id):
    with sqlite3.connect(DATABASE_PATH) as conn:
        return conn.execute(
            'SELECT request_type, account, password '
            'FROM pending_passwords WHERE user_id = ?',
            (user_id,),
        ).fetchone()


def delete_pending_password(user_id):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            'DELETE FROM pending_passwords WHERE user_id = ?',
            (user_id,),
        )


def is_processed(chat_id, message_id):
    with sqlite3.connect(DATABASE_PATH) as conn:
        return conn.execute(
            'SELECT 1 FROM processed_requests WHERE chat_id = ? AND message_id = ?',
            (chat_id, message_id),
        ).fetchone() is not None


def mark_processed(chat_id, message_id):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            'INSERT OR IGNORE INTO processed_requests '
            '(chat_id, message_id, processed_at) VALUES (?, ?, ?)',
            (
                chat_id,
                message_id,
                datetime.now().isoformat(timespec='seconds'),
            ),
        )


def save_history(**kwargs):
    """Lưu lịch sử nhưng không lưu mật khẩu."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            'INSERT INTO history '
            '(created_at, group_name, group_id, confirmer_id, confirmer_name, '
            'recipient_id, recipient_name, request_type, account) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                datetime.now().isoformat(timespec='seconds'),
                kwargs['group_name'],
                kwargs['group_id'],
                kwargs['confirmer_id'],
                kwargs['confirmer_name'],
                kwargs['recipient_id'],
                kwargs['recipient_name'],
                kwargs['request_type'],
                kwargs['account'],
            ),
        )
