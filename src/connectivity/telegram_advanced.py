
import asyncio
import logging
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message

TOKEN = '8002118889:AAFSQuXZX_bbjbaU-k2jrjda4mprbm-cLRo'
DB_NAME = 'data/chat_history.db'

def init_db():
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS messages 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, role TEXT, text TEXT, ts DATETIME)''')
    conn.commit()
    conn.close()

def save_msg(chat_id, role, text):
    conn = sqlite3.connect(DB_NAME)
    conn.execute('INSERT INTO messages (chat_id, role, text, ts) VALUES (?, ?, ?, ?)',
                 (chat_id, role, text, datetime.now()))
    conn.commit()
    conn.close()

def get_history(chat_id, limit=20):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute('SELECT role, text FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?', (chat_id, limit))
    rows = cursor.fetchall()[::-1]
    conn.close()
    return "\n".join([f"{r}: {t}" for r, t in rows])

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command('history'))
async def cmd_history(message: Message):
    hist = get_history(message.chat.id, 50)
    await message.answer(f"📜 Последние сообщения:\n\n{hist}"[:4000])

@dp.message()
async def handle_all(message: Message):
    chat_id = message.chat.id
    user_text = message.text or "[non-text]"
    save_msg(chat_id, 'User', user_text)
    
    # Retrieve history for context
    context_history = get_history(chat_id, 15)
    
    # Response indicating memory awareness
    response = f"Я вижу историю нашего чата. Ты только что сказал: {user_text}"
    
    save_msg(chat_id, 'Argos', response)
    await message.answer(response)

async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("🔱 ARGOS ADVANCED HISTORY BOT ONLINE")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
