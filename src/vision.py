"""
vision.py — Глаза Аргоса (Computer Vision)
  Анализирует скриншоты, изображения, фото с камеры через Gemini Vision.
  Fallback: базовое описание через PIL.
"""
import os
import base64
import platform
from src.argos_logger import get_logger

log = get_logger("argos.vision")

try:
    import google.generativeai as genai
    GEMINI_OK = True
except ImportError:
    genai = None
    GEMINI_OK = False

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    Image = None
    PIL_OK = False


class ArgosVision:
    def __init__(self, api_key: str = None):
        self._key = api_key or os.getenv("GEMINI_API_KEY")
        self._model = None
        if GEMINI_OK and self._key and self._key != "your_key_here":
            genai.configure(api_key=self._key)
            self._model = genai.GenerativeModel("gemini-1.5-flash")
            log.info("Vision: Gemini Vision подключён.")
        else:
            log.warning("Vision: Gemini недоступен — анализ изображений ограничен.")

    # ── СКРИНШОТ ──────────────────────────────────────────
    def screenshot(self, save_path: str = "logs/screenshot.png") -> str:
        """Делает скриншот экрана и возвращает путь к файлу."""
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        try:
            # pyautogui — кроссплатформенный
            import pyautogui
            img = pyautogui.screenshot()
            img.save(save_path)
            log.info("Скриншот: %s", save_path)
            return save_path
        except ImportError:
            pass

        # Fallback: PIL ImageGrab (Windows/macOS)
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(save_path)
            return save_path
        except Exception:
            pass

        # Linux: scrot
        if platform.system() == "Linux":
            import subprocess
            try:
                subprocess.run(["scrot", save_path], check=True)
                return save_path
            except Exception:
                pass

        return ""

    # ── АНАЛИЗ ИЗОБРАЖЕНИЯ ────────────────────────────────
    def analyze_image(self, image_path: str, question: str = "Опиши что на изображении подробно.") -> str:
        """Анализирует изображение через Gemini Vision."""
        if not os.path.exists(image_path):
            return f"❌ Файл не найден: {image_path}"

        if self._model:
            try:
                import PIL.Image
                img  = PIL.Image.open(image_path)
                resp = self._model.generate_content([question, img])
                log.info("Vision анализ: %s", image_path)
                return f"👁️ VISION АНАЛИЗ:\n{resp.text}"
            except Exception as e:
                log.error("Gemini Vision ошибка: %s", e)

        # Fallback — базовая информация через PIL
        if PIL_OK:
            try:
                img  = Image.open(image_path)
                w, h = img.size
                mode = img.mode
                return (f"👁️ Изображение: {os.path.basename(image_path)}\n"
                        f"  Размер: {w}×{h} px\n"
                        f"  Режим:  {mode}\n"
                        f"  (Для детального анализа нужен Gemini API)")
            except Exception as e:
                return f"❌ PIL ошибка: {e}"

        return "❌ Для анализа изображений установи: pip install google-generativeai Pillow"

    # ── СКРИНШОТ + АНАЛИЗ ─────────────────────────────────
    def look_at_screen(self, question: str = "Что происходит на экране? Опиши кратко.") -> str:
        """Делает скриншот и сразу анализирует его."""
        path = self.screenshot()
        if not path:
            return "❌ Не удалось сделать скриншот. Установи: pip install pyautogui"
        return self.analyze_image(path, question)

    # ── КАМЕРА ────────────────────────────────────────────
    def capture_camera(self, save_path: str = "logs/camera.jpg") -> str:
        """Снимает кадр с веб-камеры."""
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return "❌ Камера недоступна."
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(save_path, frame)
                log.info("Камера: %s", save_path)
                return save_path
            return "❌ Кадр не получен."
        except ImportError:
            return "❌ Установи: pip install opencv-python"
        except Exception as e:
            return f"❌ Камера: {e}"

    def look_through_camera(self, question: str = "Что ты видишь? Опиши подробно.") -> str:
        """Снимает с камеры и анализирует."""
        path = self.capture_camera()
        if path.startswith("❌"):
            return path
        return self.analyze_image(path, question)

    # ── АНАЛИЗ ФАЙЛА ──────────────────────────────────────
    def analyze_file(self, path: str) -> str:
        """Анализирует любой переданный файл-изображение."""
        supported = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
        if not any(path.lower().endswith(ext) for ext in supported):
            return f"❌ Неподдерживаемый формат. Поддерживаю: {', '.join(supported)}"
        return self.analyze_image(path)
