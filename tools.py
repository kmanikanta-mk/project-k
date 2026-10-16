
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DATABASE_PATH", Path(__file__).with_name("assistant.db")))


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT,
                priority TEXT DEFAULT 'medium',
                completed INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL
            )
        """)


def add_task(title, due_date=None, priority="medium"):
    if not title.strip():
        return "Task title cannot be empty."

    if priority not in ("low", "medium", "high"):
        priority = "medium"

    with connect_db() as conn:
        cur = conn.execute(
            """INSERT INTO tasks (title, due_date, priority)
               VALUES (?, ?, ?)""",
            (title.strip(), due_date, priority)
        )
        return f"Task saved successfully. ID: {cur.lastrowid}"


def list_tasks():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY completed, id DESC"
        ).fetchall()

    return [dict(row) for row in rows]


def complete_task(task_id):
    with connect_db() as conn:
        cur = conn.execute(
            "UPDATE tasks SET completed = 1 WHERE id = ?",
            (task_id,)
        )

    return "Task completed." if cur.rowcount else "Task not found."


def save_memory(content):
    if not content.strip():
        return "Memory cannot be empty."

    with connect_db() as conn:
        cur = conn.execute(
            "INSERT INTO memories (content) VALUES (?)",
            (content.strip(),)
        )

    return f"Memory saved locally. ID: {cur.lastrowid}"


def list_memories():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY id DESC"
        ).fetchall()

    return [dict(row) for row in rows]


def search_memory(query):
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM memories WHERE content LIKE ?",
            (f"%{query}%",)
        ).fetchall()

    return [dict(row) for row in rows]


def delete_memory(memory_id):
    with connect_db() as conn:
        cur = conn.execute(
            "DELETE FROM memories WHERE id = ?",
            (memory_id,)
        )

    return "Memory deleted." if cur.rowcount else "Memory not found."


def summarize_file(file_path):
    from model import ask_local_model

    path = Path(file_path).expanduser()

    if not path.is_file():
        return "File not found."

    if path.suffix.lower() not in (".txt", ".md"):
        return "Please choose a .txt or .md file."

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return f"Could not read file: {error}"

    if not content.strip():
        return "The file is empty."

    content = content[:20000]

    return ask_local_model(
        "Summarize this document. Explain the key points:\n\n" + content,
        "You are a helpful document summarization assistant."
    )


initialize_database()

