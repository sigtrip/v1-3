"""
icon_generator.py — Генератор иконок Аргоса
  Рисует иконку программно через PIL — глаз в квантовом стиле.
  Создаёт: argos_icon.ico (Windows), argos_icon.icns (macOS),
           argos_icon.png (Linux/Android), иконки разных размеров.
  Вызывается автономно по запросу пользователя.
"""

import io
import math
import os
import struct

from src.argos_logger import get_logger

log = get_logger("argos.icons")

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    PIL_OK = True
except ImportError:
    PIL_OK = False

ASSETS = "assets"


class ArgosIconGenerator:

    # ── РИСУЕМ ИКОНКУ ─────────────────────────────────────
    def _draw_icon(self, size: int) -> "Image":
        """Рисует иконку Аргоса: всевидящее oko в квантовом стиле."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy = size // 2, size // 2
        r = size // 2

        # — Фон: тёмно-синий круг с градиентом ────────────
        for i in range(r, 0, -1):
            ratio = i / r
            b = int(20 + 40 * (1 - ratio))
            g = int(5 + 15 * (1 - ratio))
            a = 255
            draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(0, g, b, a))

        # — Внешнее кольцо (cyan glow) ─────────────────────
        ring_w = max(2, size // 24)
        for offset in range(ring_w + 4, 0, -1):
            alpha = int(80 * (1 - offset / (ring_w + 4)))
            draw.ellipse(
                [cx - r + offset, cy - r + offset, cx + r - offset, cy + r - offset],
                outline=(0, 255, 255, alpha),
                width=1,
            )
        draw.ellipse(
            [cx - r + ring_w, cy - r + ring_w, cx + r - ring_w, cy + r - ring_w],
            outline=(0, 220, 220, 255),
            width=ring_w,
        )

        # — Сетка квантовых линий ──────────────────────────
        grid_lines = 6
        for i in range(1, grid_lines):
            x = cx - r + int(2 * r * i / grid_lines)
            y = cy - r + int(2 * r * i / grid_lines)
            alpha = 25
            draw.line([(x, cy - r), (x, cy + r)], fill=(0, 100, 120, alpha), width=1)
            draw.line([(cx - r, y), (cx + r, y)], fill=(0, 100, 120, alpha), width=1)

        # — Диагональные линии (матричный эффект) ──────────
        for i in range(-3, 4):
            offset = i * (size // 5)
            alpha = 15
            draw.line([(cx - r, cy - r + offset), (cx + r, cy + r + offset)], fill=(0, 80, 100, alpha), width=1)

        # — Внутренний глаз ────────────────────────────────
        eye_rx = int(r * 0.52)
        eye_ry = int(r * 0.32)

        # Радужка (тёмно-синяя)
        draw.ellipse([cx - eye_rx, cy - eye_ry, cx + eye_rx, cy + eye_ry], fill=(0, 15, 35, 255))

        # Веки — верхнее и нижнее (заострённые)
        eyelid_pts_top = [
            (cx - eye_rx, cy),
            (cx - eye_rx // 2, cy - eye_ry - eye_ry // 3),
            (cx, cy - eye_ry - eye_ry // 2),
            (cx + eye_rx // 2, cy - eye_ry - eye_ry // 3),
            (cx + eye_rx, cy),
        ]
        eyelid_pts_bot = [
            (cx - eye_rx, cy),
            (cx - eye_rx // 2, cy + eye_ry + eye_ry // 4),
            (cx, cy + eye_ry + eye_ry // 3),
            (cx + eye_rx // 2, cy + eye_ry + eye_ry // 4),
            (cx + eye_rx, cy),
        ]
        # Контур глаза
        all_pts = eyelid_pts_top + eyelid_pts_bot[::-1]
        draw.polygon(all_pts, fill=(0, 15, 35, 255))
        draw.line(eyelid_pts_top + [eyelid_pts_top[0]], fill=(0, 200, 220, 200), width=max(1, size // 48))
        draw.line(eyelid_pts_bot + [eyelid_pts_bot[0]], fill=(0, 200, 220, 200), width=max(1, size // 48))

        # Радужка (iris) — cyan кольцо
        iris_r = int(r * 0.22)
        for offset in range(4, 0, -1):
            alpha = 60 * offset // 4
            draw.ellipse(
                [cx - iris_r - offset, cy - iris_r - offset, cx + iris_r + offset, cy + iris_r + offset],
                outline=(0, 255, 255, alpha),
                width=1,
            )
        draw.ellipse(
            [cx - iris_r, cy - iris_r, cx + iris_r, cy + iris_r],
            fill=(0, 30, 60, 255),
            outline=(0, 200, 255, 255),
            width=max(1, size // 32),
        )

        # Зрачок (pupil) — чёрный
        pupil_r = int(r * 0.12)
        draw.ellipse([cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r], fill=(0, 5, 10, 255))

        # Блик на зрачке
        shine_r = max(2, pupil_r // 3)
        draw.ellipse(
            [cx - pupil_r + shine_r, cy - pupil_r + shine_r, cx - pupil_r + shine_r * 3, cy - pupil_r + shine_r * 3],
            fill=(200, 255, 255, 180),
        )

        # — Квантовые точки вокруг ─────────────────────────
        num_dots = 8
        dot_orbit = int(r * 0.72)
        dot_r = max(2, size // 30)
        for i in range(num_dots):
            angle = 2 * math.pi * i / num_dots - math.pi / 2
            dx = int(cx + dot_orbit * math.cos(angle))
            dy = int(cy + dot_orbit * math.sin(angle))
            # Glow
            for g in range(dot_r + 3, 0, -1):
                alpha = int(80 * (1 - g / (dot_r + 3)))
                col = (0, 200, 255, alpha) if i % 2 == 0 else (100, 0, 200, alpha)
                draw.ellipse([dx - g, dy - g, dx + g, dy + g], fill=col)
            col = (0, 255, 255, 255) if i % 2 == 0 else (150, 50, 255, 255)
            draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r], fill=col)

        # — Финальный glow-blur ────────────────────────────
        if size >= 64:
            glow = img.copy().filter(ImageFilter.GaussianBlur(radius=size // 20))
            img = Image.alpha_composite(glow, img)

        return img

    # ── СОХРАНЕНИЕ ФОРМАТОВ ───────────────────────────────
    def generate_png(self, size: int = 512, path: str = None) -> str:
        if not PIL_OK:
            return "❌ Установи: pip install Pillow"
        os.makedirs(ASSETS, exist_ok=True)
        path = path or f"{ASSETS}/argos_icon_{size}.png"
        img = self._draw_icon(size)
        img.save(path, "PNG")
        log.info("PNG иконка: %s (%dx%d)", path, size, size)
        return path

    def generate_ico(self, path: str = None) -> str:
        """ICO для Windows — несколько размеров в одном файле."""
        if not PIL_OK:
            return "❌ Установи: pip install Pillow"
        os.makedirs(ASSETS, exist_ok=True)
        path = path or f"{ASSETS}/argos_icon.ico"
        sizes = [16, 32, 48, 64, 128, 256]
        imgs = [self._draw_icon(s).convert("RGBA") for s in sizes]
        # PIL сохраняет ICO со всеми размерами
        imgs[0].save(path, format="ICO", sizes=[(s, s) for s in sizes], append_images=imgs[1:])
        sz = os.path.getsize(path) // 1024
        log.info("ICO иконка: %s (%dKB)", path, sz)
        return path

    def generate_icns(self, path: str = None) -> str:
        """ICNS для macOS — упакованный формат Apple."""
        if not PIL_OK:
            return "❌ Установи: pip install Pillow"
        os.makedirs(ASSETS, exist_ok=True)
        path = path or f"{ASSETS}/argos_icon.icns"

        # ICNS структура: заголовок + иконки разных размеров
        icns_sizes = {
            b"is32": 16,
            b"il32": 32,
            b"ih32": 48,
            b"it32": 128,
            b"ic08": 256,
            b"ic09": 512,
        }
        buf = io.BytesIO()
        buf.write(b"icns")  # magic
        size_pos = buf.tell()
        buf.write(b"\x00\x00\x00\x00")  # размер (заполним потом)

        for tag, sz in icns_sizes.items():
            img = self._draw_icon(sz).convert("RGBA")
            png_buf = io.BytesIO()
            img.save(png_buf, "PNG")
            png_data = png_buf.getvalue()
            # Для it32 (128) используем raw, для остальных PNG
            if sz == 128:
                buf.write(tag)
                chunk_size = 8 + len(png_data)
                buf.write(struct.pack(">I", chunk_size))
                buf.write(png_data)
            else:
                buf.write(tag)
                chunk_size = 8 + len(png_data)
                buf.write(struct.pack(">I", chunk_size))
                buf.write(png_data)

        total = buf.tell()
        buf.seek(size_pos)
        buf.write(struct.pack(">I", total))

        with open(path, "wb") as f:
            f.write(buf.getvalue())
        log.info("ICNS иконка: %s", path)
        return path

    def generate_all(self) -> str:
        """Генерирует все форматы иконок."""
        results = ["🎨 ГЕНЕРАЦИЯ ИКОНОК АРГОСА:"]
        errors = []

        # PNG набор
        for size in [16, 32, 48, 64, 128, 256, 512]:
            try:
                p = self.generate_png(size)
                results.append(f"  ✅ PNG {size}×{size} → {p}")
            except Exception as e:
                errors.append(f"PNG {size}: {e}")

        # ICO (Windows)
        try:
            p = self.generate_ico()
            results.append(f"  ✅ ICO (Win) → {p}")
        except Exception as e:
            errors.append(f"ICO: {e}")

        # ICNS (macOS)
        try:
            p = self.generate_icns()
            results.append(f"  ✅ ICNS (Mac) → {p}")
        except Exception as e:
            errors.append(f"ICNS: {e}")

        # Android (круглая 192px)
        try:
            p = self.generate_png(192, f"{ASSETS}/argos_android.png")
            results.append(f"  ✅ Android 192×192 → {p}")
        except Exception as e:
            errors.append(f"Android: {e}")

        if errors:
            results.append(f"\n  ⚠️ Ошибки: {', '.join(errors)}")

        results.append(f"\n  📂 Все иконки в папке: {ASSETS}/")
        return "\n".join(results)
