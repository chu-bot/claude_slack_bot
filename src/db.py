import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent.parent / "data" / "bot.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            repo_path TEXT,
            channel_id TEXT,
            first_prompt TEXT,
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS prompt_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            channel_id TEXT,
            slack_user_id TEXT,
            slack_username TEXT,
            prompt TEXT,
            response_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)
    conn.commit()
    conn.close()


def create_session(channel_id: str, repo_path: str, first_prompt: str) -> int:
    conn = get_connection()
    conn.execute("UPDATE sessions SET is_active = FALSE WHERE channel_id = ?", (channel_id,))
    cursor = conn.execute(
        "INSERT INTO sessions (channel_id, repo_path, first_prompt, is_active) VALUES (?, ?, ?, TRUE)",
        (channel_id, repo_path, first_prompt),
    )
    session_db_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_db_id


def update_session_claude_id(db_id: int, claude_session_id: str):
    conn = get_connection()
    conn.execute("UPDATE sessions SET session_id = ? WHERE id = ?", (claude_session_id, db_id))
    conn.commit()
    conn.close()


def get_active_session(channel_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM sessions WHERE channel_id = ? AND is_active = TRUE", (channel_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_active_session(channel_id: str, session_db_id: int):
    conn = get_connection()
    conn.execute("UPDATE sessions SET is_active = FALSE WHERE channel_id = ?", (channel_id,))
    conn.execute(
        "UPDATE sessions SET is_active = TRUE, last_active = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), session_db_id),
    )
    conn.commit()
    conn.close()


def get_recent_sessions(channel_id: str, limit: int = 10) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.*, COUNT(p.id) as message_count
           FROM sessions s
           LEFT JOIN prompt_log p ON p.session_id = s.id
           WHERE s.channel_id = ?
           GROUP BY s.id
           ORDER BY s.last_active DESC
           LIMIT ?""",
        (channel_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_by_id(session_db_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_db_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def log_prompt(session_db_id: int, channel_id: str, slack_user_id: str, slack_username: str, prompt: str, response_summary: str = ""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO prompt_log (session_id, channel_id, slack_user_id, slack_username, prompt, response_summary) VALUES (?, ?, ?, ?, ?, ?)",
        (session_db_id, channel_id, slack_user_id, slack_username, prompt, response_summary),
    )
    conn.execute(
        "UPDATE sessions SET last_active = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), session_db_id),
    )
    conn.commit()
    conn.close()


def update_prompt_response(session_db_id: int, prompt: str, response_summary: str):
    conn = get_connection()
    conn.execute(
        """UPDATE prompt_log SET response_summary = ?
           WHERE id = (
               SELECT id FROM prompt_log
               WHERE session_id = ? AND prompt = ?
               ORDER BY created_at DESC LIMIT 1
           )""",
        (response_summary, session_db_id, prompt),
    )
    conn.commit()
    conn.close()
