"""memory.py — SQLite-память Аргоса"""
import sqlite3, json, os
from datetime import datetime
from src.argos_logger import get_logger
log = get_logger("argos.memory")

DB_PATH = os.getenv("ARGOS_DB", "data/argos_memory.db")

class ArgosMemory:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._create_tables()
        log.info("SQLite memory: %s", DB_PATH)

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT DEFAULT 'general',
                key TEXT NOT NULL,
                value TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                text TEXT,
                category TEXT DEFAULT 'ai',
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    def save(self, key: str, value: str, category: str = "general") -> str:
        self.conn.execute(
            "INSERT OR REPLACE INTO facts (category, key, value) VALUES (?,?,?)",
            (category, key, str(value))
        )
        self.conn.commit()
        return f"✅ Запомнил: {key}"

    def get(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM facts WHERE key=? ORDER BY id DESC LIMIT 1", (key,)
        ).fetchone()
        return row[0] if row else None

    def get_all_facts(self) -> list:
        return self.conn.execute(
            "SELECT category, key, value, created_at FROM facts ORDER BY id DESC LIMIT 200"
        ).fetchall()

    def log_chat(self, role: str, text: str, category: str = "ai"):
        self.conn.execute(
            "INSERT INTO chat_history (role, text, category) VALUES (?,?,?)",
            (role, text, category)
        )
        self.conn.commit()

    def get_chat_history(self, limit: int = 100) -> list:
        rows = self.conn.execute(
            "SELECT role, text, category FROM chat_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"role": r[0], "text": r[1], "category": r[2]} for r in rows]

    def summary(self) -> str:
        facts = self.get_all_facts()
        if not facts:
            return "🧠 Память пуста."
        lines = ["🧠 ИЗВЕСТНЫЕ ФАКТЫ:"]
        for cat, key, val, ts in facts[:20]:
            lines.append(f"  [{cat}] {key} = {val}")
        return "\n".join(lines)
