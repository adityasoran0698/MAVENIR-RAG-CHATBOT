import sqlite3
from pathlib import Path
from datetime import datetime, timezone

# =========================================================
# DATABASE PATH
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

DB_PATH = DATA_DIR / "app.sqlite"


# =========================================================
# CONNECTION
# =========================================================


def get_connection():
    conn = sqlite3.connect(
        str(DB_PATH),
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# INIT SCHEMA
# =========================================================


def init_schema():

    conn = get_connection()

    try:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New conversation',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

        conn.commit()

    finally:

        conn.close()


# =========================================================
# THREAD EXISTS
# =========================================================


def thread_exists(
    thread_id: str,
) -> bool:

    conn = get_connection()

    try:

        row = conn.execute(
            """
            SELECT 1
            FROM threads
            WHERE id = ?
            LIMIT 1
            """,
            (thread_id,),
        ).fetchone()

        return row is not None

    finally:

        conn.close()


# =========================================================
# CREATE THREAD
# =========================================================


def create_thread(
    thread_id: str,
    title: str = "New conversation",
):

    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()

    try:

        conn.execute(
            """
            INSERT OR IGNORE INTO threads
            (
                id,
                title,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                thread_id,
                title,
                now,
                now,
            ),
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# TOUCH THREAD
# =========================================================


def touch_thread(
    thread_id: str,
    title: str | None = None,
):

    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()

    try:

        if title is not None:

            conn.execute(
                """
                UPDATE threads
                SET
                    title = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    title,
                    now,
                    thread_id,
                ),
            )

        else:

            conn.execute(
                """
                UPDATE threads
                SET updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    thread_id,
                ),
            )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# LIST THREADS
# =========================================================


def list_threads():

    conn = get_connection()

    try:

        rows = conn.execute("""
            SELECT
                id,
                title,
                created_at,
                updated_at
            FROM threads
            ORDER BY updated_at DESC
            """).fetchall()

        return [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    finally:

        conn.close()
