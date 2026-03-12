
import asyncio
import logging
import sqlite3
import os
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai

TOKEN = "8002118889:AAFSQuXZX_bbjbaU-k2jrjda4mprbm-cLRo"
genai.configure(api_key="AQ.Ab8RN6KHlyooHNq9vexZxViV0zAFXDLuwDRwVjA8sgaekhnQQw")

bot = Bot(token=TOKEN)
dp = Dispatcher()
DB_NAME = "data/chat_history.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    os.makedirs("temp_audio", exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, role TEXT, text TEXT, ts DATETIME)")
    conn.commit()
    conn.close()

async def get_vision_analysis(photo_path, prompt="Что на этой картинке?"):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        img = genai.upload_file(photo_path)
        response = model.generate_content([prompt, img])
        return response.text
    except Exception as e:
        return f"Ошибка Vision: {e}"

@dp.message(F.photo)
async def handle_photo(message: Message):
    photo = message.photo[-1]
    file_path = f"temp_{photo.file_id}.jpg"
    await bot.download(photo, destination=file_path)
    await message.answer("👁️ Вижу изображение, анализирую...")
    analysis = await get_vision_analysis(file_path)
    await message.answer(f"Результат: {analysis}")
    os.remove(file_path)

@dp.message(F.voice)
async def handle_voice(message: Message):
    voice = message.voice
    file_id = voice.file_id
    file = await bot.get_file(file_id)
    file_path = f"temp_{file_id}.ogg"
    await bot.download(file, destination=file_path)
    
    # Convert and Recognize (Simplified logic for Colab)
    await message.answer("👂 Слышу ваш голос, расшифровываю...")
    # Note: In a full environment, you'd use ffmpeg to convert ogg to wav
    await message.answer("Голосовой ввод принят (требуется ffmpeg для полной обработки в Colab).")

@dp.message()
async def handle_text(message: Message):
    text = message.text
    await message.answer(f"Получил текст: {text}")

async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("🚀 Multimodal Bot Started!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
