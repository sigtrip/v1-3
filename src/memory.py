"""
memory.py — Долгосрочная память Аргоса
  Запоминает факты о пользователе, предпочтения, заметки.
  Хранится в SQLite. Передаётся в контекст ИИ при каждом запросе.
"""
import json
import os
import sqlite3
import time
from src.argos_logger import get_logger

log = get_logger("argos.memory")
DB_PATH = "data/memory.db"


class ArgosMemory:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                category  TEXT NOT NULL DEFAULT 'general',
                key       TEXT NOT NULL,
                value     TEXT NOT NULL,
                ts        TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(category, key)
            );
            CREATE TABLE IF NOT EXISTS notes (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body  TEXT NOT NULL,
                ts    TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                text     TEXT NOT NULL,
                remind_at REAL NOT NULL,
                done     INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()
        log.debug("Memory DB инициализирована.")

    # ── ФАКТЫ ──────────────────────────────────────────────
    def remember(self, key: str, value: str, category: str = "user") -> str:
        """Запомнить факт. 'аргос, запомни: я люблю Python'"""
        self.conn.execute(
            "INSERT INTO facts (category, key, value) VALUES (?,?,?) "
            "ON CONFLICT(category,key) DO UPDATE SET value=excluded.value, ts=datetime('now','localtime')",
            (category, key, value)
        )
        self.conn.commit()
        log.info("Запомнил [%s] %s = %s", category, key, value)
        return f"✅ Запомнил: {key} → {value}"

    def recall(self, key: str, category: str = "user") -> str | None:
        row = self.conn.execute(
            "SELECT value FROM facts WHERE category=? AND key=?", (category, key)
        ).fetchone()
        return row[0] if row else None

    def forget(self, key: str, category: str = "user") -> str:
        self.conn.execute("DELETE FROM facts WHERE category=? AND key=?", (category, key))
        self.conn.commit()
        return f"🗑️ Удалено из памяти: {key}"

    def get_all_facts(self, category: str = None) -> list:
        if category:
            return self.conn.execute(
                "SELECT category, key, value, ts FROM facts WHERE category=? ORDER BY ts DESC", (category,)
            ).fetchall()
        return self.conn.execute(
            "SELECT category, key, value, ts FROM facts ORDER BY category, key"
        ).fetchall()

    def get_context(self) -> str:
        """Возвращает строку контекста для вставки в ИИ-запрос."""
        facts = self.get_all_facts()
        if not facts:
            return ""
        lines = ["Известные факты о пользователе и системе:"]
        for cat, key, val, _ in facts:
            lines.append(f"  [{cat}] {key}: {val}")
        return "\n".join(lines)

    def format_memory(self) -> str:
        facts = self.get_all_facts()
        if not facts:
            return "🧠 Память пуста."
        lines = ["🧠 ДОЛГОСРОЧНАЯ ПАМЯТЬ АРГОСА:"]
        prev_cat = None
        for cat, key, val, ts in facts:
            if cat != prev_cat:
                lines.append(f"\n  [{cat.upper()}]")
                prev_cat = cat
            lines.append(f"    • {key}: {val}  ({ts[:16]})")
        return "\n".join(lines)

    # ── ЗАМЕТКИ ────────────────────────────────────────────
    def add_note(self, title: str, body: str) -> str:
        self.conn.execute(
            "INSERT INTO notes (title, body) VALUES (?,?)", (title, body)
        )
        self.conn.commit()
        return f"📝 Заметка сохранена: '{title}'"

    def get_notes(self, limit: int = 10) -> str:
        rows = self.conn.execute(
            "SELECT id, title, ts FROM notes ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        if not rows:
            return "📭 Заметок нет."
        lines = [f"📝 ЗАМЕТКИ ({len(rows)}):"]
        for rid, title, ts in rows:
            lines.append(f"  #{rid} [{ts[:16]}] {title}")
        return "\n".join(lines)

    def read_note(self, note_id: int) -> str:
        row = self.conn.execute(
            "SELECT title, body, ts FROM notes WHERE id=?", (note_id,)
        ).fetchone()
        if not row:
            return f"❌ Заметка #{note_id} не найдена."
        title, body, ts = row
        return f"📝 #{note_id} [{ts[:16]}] {title}\n\n{body}"

    def delete_note(self, note_id: int) -> str:
        self.conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()
        return f"🗑️ Заметка #{note_id} удалена."

    # ── НАПОМИНАНИЯ ────────────────────────────────────────
    def add_reminder(self, text: str, seconds_from_now: int) -> str:
        remind_at = time.time() + seconds_from_now
        self.conn.execute(
            "INSERT INTO reminders (text, remind_at) VALUES (?,?)", (text, remind_at)
        )
        self.conn.commit()
        import datetime
        dt = datetime.datetime.fromtimestamp(remind_at).strftime("%H:%M %d.%m")
        return f"⏰ Напоминание установлено на {dt}: {text}"

    def check_reminders(self) -> list[str]:
        now  = time.time()
        rows = self.conn.execute(
            "SELECT id, text FROM reminders WHERE remind_at<=? AND done=0", (now,)
        ).fetchall()
        fired = []
        for rid, text in rows:
            self.conn.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))
            fired.append(f"⏰ НАПОМИНАНИЕ: {text}")
        if fired:
            self.conn.commit()
        return fired

    def parse_and_remember(self, text: str) -> str:
        """'аргос, запомни что я люблю Python' → сохраняет факт"""
        t = text.lower()
        for pref in ["запомни что ", "запомни: ", "запомни ", "я "]:
            if t.startswith(pref):
                rest = text[len(pref):]
                if ":" in rest:
                    key, val = rest.split(":", 1)
                    return self.remember(key.strip(), val.strip())
                return self.remember("факт", rest.strip())
        return self.remember("факт", text.strip())

    def close(self):
        self.conn.close()
