
import asyncio
import logging
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import openai

TOKEN = "8002118889:AAFSQuXZX_bbjbaU-k2jrjda4mprbm-cLRo"
openai.api_key = "ВАШ_OPENAI_API_KEY"

bot = Bot(token=TOKEN)
dp = Dispatcher()
DB_NAME = "data/chat_history.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            text TEXT,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_message(chat_id, user_id, username, full_name, text):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (chat_id, user_id, username, full_name, text, date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (chat_id, user_id, username, full_name, text, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_full_history(chat_id, limit=100):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT full_name, text, date FROM messages 
        WHERE chat_id = ? ORDER BY id ASC LIMIT ?
    """, (chat_id, limit))
    rows = cur.fetchall()
    conn.close()
    if not rows: return "История пуста."
    return "\n".join([f"[{date[:19]}] {name}: {text}" for name, text, date in rows])

async def get_gpt_response(chat_id, user_message):
    history_text = get_full_history(chat_id, limit=80)
    system_prompt = f"""Ты умный дружелюбный помощник.
У тебя есть полная история чата ниже. Отвечай максимально полезно.

=== ВСЯ ИСТОРИЯ ЧАТА ===
{history_text}
=== КОНЕЦ ИСТОРИИ ===

Пользователь сейчас написал: {user_message}
Отвечай только на русском, коротко и по делу."""
    try:
        response = await asyncio.to_thread(
            openai.chat.completions.create if hasattr(openai, 'chat') else openai.ChatCompletion.create,
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip() if hasattr(response, 'choices') else response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Ошибка OpenAI: {e}"

@dp.message(Command("history"))
async def cmd_history(message: Message):
    hist = get_full_history(message.chat.id, limit=50)
    await message.answer("📜 Последние 50 сообщений:\n\n" + hist[:4000])

@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM messages WHERE chat_id = ?", (message.chat.id,))
    conn.commit()
    conn.close()
    await message.answer("✅ История очищена.")

@dp.message()
async def all_messages(message: Message):
    text = message.text or f"[Content: {message.content_type}]"
    save_message(message.chat.id, message.from_user.id, message.from_user.username, message.from_user.full_name, text)
    gpt_text = await get_gpt_response(message.chat.id, text)
    await message.answer(gpt_text)

async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
