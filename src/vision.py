"""vision.py — Анализ изображений и экрана через Gemini Vision"""
from __future__ import annotations
import os, base64
from pathlib import Path
from src.argos_logger import get_logger
log = get_logger("argos.vision")

class ArgosVision:
    def __init__(self, core=None):
        self.core = core
        self.api_key = os.getenv("GEMINI_API_KEY","")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def analyze_file(self, path: str, question: str = "Что на изображении?") -> str:
        if not self.available:
            return "❌ GEMINI_API_KEY не установлен."
        try:
            import google.generativeai as genai
            from PIL import Image
            genai.configure(api_key=self.api_key)
            img = Image.open(path)
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content([question, img])
            return f"👁️ Vision: {resp.text}"
        except ImportError:
            return "❌ Установи: pip install google-generativeai Pillow"
        except Exception as e:
            return f"❌ Vision error: {e}"

    def analyze_screen(self, question: str = "Что на экране?") -> str:
        if not self.available:
            return "❌ GEMINI_API_KEY не установлен."
        try:
            import pyautogui
            from io import BytesIO
            screenshot = pyautogui.screenshot()
            buf = BytesIO()
            screenshot.save(buf, format="PNG")
            buf.seek(0)
            import google.generativeai as genai
            from PIL import Image
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content([question, Image.open(buf)])
            return f"👁️ Экран: {resp.text}"
        except Exception as e:
            return f"❌ Screen vision error: {e}"

    def status(self) -> str:
        return (f"👁️ Vision: {'✅ готов' if self.available else '❌ нет GEMINI_API_KEY'}\n"
                f"  Модель: gemini-1.5-flash")
