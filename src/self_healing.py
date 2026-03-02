"""
self_healing.py — Self-Healing Engine
    Модуль «бессмертия»: автоматическое обнаружение, диагностика
    и коррекция ошибок в Python-коде Аргоса.

    Стратегии:
    1. Syntax fix: ast.parse → автоисправление типичных ошибок
    2. Import fix: подстановка fallback при ImportError
    3. Runtime patch: обёртка config + retry при RuntimeError
    4. Hot-reload: перезагрузка модуля после патча
"""
import os
import re
import ast
import sys
import time
import json
import traceback
import threading
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.argos_logger import get_logger

log = get_logger("argos.healing")


class HealingRecord:
    """Запись об исцелении."""
    __slots__ = ("ts", "module", "error_type", "error_msg",
                 "strategy", "success", "patch_summary")

    def __init__(self, module: str, error_type: str, error_msg: str,
                 strategy: str, success: bool, patch_summary: str = ""):
        self.ts = time.time()
        self.module = module
        self.error_type = error_type
        self.error_msg = error_msg
        self.strategy = strategy
        self.success = success
        self.patch_summary = patch_summary

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "module": self.module,
            "error_type": self.error_type,
            "error_msg": self.error_msg[:200],
            "strategy": self.strategy,
            "success": self.success,
            "patch_summary": self.patch_summary[:200],
        }


class SelfHealingEngine:
    """
    Self-Healing Engine — автоматическое исправление ошибок.

    Поддерживает:
    - Перехват исключений через sys.excepthook
    - Синтаксическая валидация через ast.parse
    - Автоматический backup перед патчем
    - Лимит попыток исцеления на модуль
    - Hot-reload после успешного исправления
    """

    VERSION = "1.0.0"
    MAX_HEAL_ATTEMPTS = 3
    BACKUP_DIR = "builds/snapshots/healing"

    def __init__(self, core=None):
        self.core = core
        self._enabled = os.getenv("ARGOS_SELF_HEALING", "on").strip().lower() \
            not in {"0", "off", "false", "no", "нет"}
        self._lock = threading.Lock()
        self._history: List[HealingRecord] = []
        self._attempt_counts: Dict[str, int] = {}
        self._original_excepthook = sys.excepthook
        self._intercepting = False

        os.makedirs(self.BACKUP_DIR, exist_ok=True)
        log.info("SelfHealingEngine v%s | enabled=%s", self.VERSION, self._enabled)

    # ── In-memory healing API (для evolution) ───────────
    def _extract_code(self, text: str) -> str:
        """Извлекает чистый код из ответа ИИ (с/без markdown fence)."""
        payload = (text or "").strip()
        m = re.search(r"```python\n(.*?)\n```", payload, re.DOTALL)
        if m:
            return m.group(1).strip()
        m = re.search(r"```\n(.*?)\n```", payload, re.DOTALL)
        if m:
            return m.group(1).strip()
        return payload

    def validate_code(self, code: str) -> Tuple[bool, str]:
        """Проверяет код на синтаксические ошибки через ast.parse."""
        try:
            ast.parse(code)
            return True, "OK"
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} (line {e.lineno}, col {e.offset})"
        except Exception as e:
            return False, f"UnexpectedError: {e}"

    def heal_code(self, broken_code: str, error_msg: str) -> Optional[str]:
        """Лечит код в памяти через доступное ИИ-ядро и возвращает исправленный код."""
        if not self.core:
            log.warning("Self-Healing: core не подключен, heal_code недоступен")
            return None

        system_prompt = (
            "Ты — Self-Healing Engine системы Argos. "
            "Исправь Python-код, который не проходит компиляцию. "
            "Верни только исправленный код без пояснений, строго в ```python ... ```."
        )
        user_prompt = f"ERROR:\n{error_msg}\n\nBROKEN_CODE:\n{broken_code}"

        try:
            ai_response = None
            if hasattr(self.core, "_ask_consensus") and getattr(self.core, "ai_mode", "") == "auto":
                ai_response = self.core._ask_consensus(system_prompt, user_prompt)
            elif getattr(self.core, "ai_mode", "") == "watsonx" and hasattr(self.core, "_ask_watsonx"):
                ai_response = self.core._ask_watsonx(system_prompt, user_prompt)
            elif hasattr(self.core, "_ask_gemini") and getattr(self.core, "model", None):
                ai_response = self.core._ask_gemini(system_prompt, user_prompt)
            elif hasattr(self.core, "_ask_ollama"):
                ai_response = self.core._ask_ollama(system_prompt, user_prompt)

            if not ai_response:
                return None
            return self._extract_code(ai_response)
        except Exception as e:
            log.error("Self-Healing heal_code error: %s", e)
            return None

    # ── Перехват исключений ──────────────────────────────
    def start_intercepting(self) -> str:
        """Устанавливает глобальный перехватчик исключений."""
        if self._intercepting:
            return "🩹 Self-Healing: перехват уже активен."
        self._original_excepthook = sys.excepthook
        sys.excepthook = self._global_except_hook
        self._intercepting = True
        log.info("Self-Healing: excepthook установлен")
        return "🩹 Self-Healing: перехват исключений активирован."

    def stop_intercepting(self) -> str:
        sys.excepthook = self._original_excepthook
        self._intercepting = False
        return "🩹 Self-Healing: перехват отключён."

    def _global_except_hook(self, exc_type, exc_value, exc_tb):
        """Глобальный обработчик: пытается исцелить и логирует."""
        # сначала логируем как обычно
        self._original_excepthook(exc_type, exc_value, exc_tb)

        if not self._enabled:
            return

        # определяем модуль, где произошла ошибка
        module_name = self._extract_module_from_tb(exc_tb)
        if not module_name:
            return

        self.attempt_heal(module_name, exc_type.__name__, str(exc_value))

    # ── Основной метод исцеления ─────────────────────────
    def attempt_heal(self, module_path: str, error_type: str,
                     error_msg: str) -> bool:
        """
        Пытается исцелить модуль. Возвращает True при успехе.
        """
        with self._lock:
            count = self._attempt_counts.get(module_path, 0)
            if count >= self.MAX_HEAL_ATTEMPTS:
                log.warning("Healing: лимит попыток для %s (%d)", module_path, count)
                rec = HealingRecord(module_path, error_type, error_msg,
                                    "limit_reached", False, f"max attempts ({count})")
                self._history.append(rec)
                return False
            self._attempt_counts[module_path] = count + 1

        # Поиск файла
        file_path = self._resolve_file(module_path)
        if not file_path or not os.path.isfile(file_path):
            log.warning("Healing: файл не найден для %s", module_path)
            return False

        log.info("Healing: попытка исцеления %s (%s: %s)",
                 module_path, error_type, error_msg[:80])

        # Backup
        self._backup(file_path)

        # Попытки стратегий
        strategies = [
            ("syntax_fix", self._strategy_syntax_fix),
            ("import_fix", self._strategy_import_fix),
            ("runtime_patch", self._strategy_runtime_patch),
        ]

        for name, strategy_fn in strategies:
            try:
                success, summary = strategy_fn(file_path, error_type, error_msg)
                rec = HealingRecord(module_path, error_type, error_msg,
                                    name, success, summary)
                self._history.append(rec)
                if success:
                    log.info("Healing SUCCESS: %s via %s — %s", module_path, name, summary)
                    self._try_hot_reload(module_path)
                    return True
            except Exception as e:
                log.error("Healing strategy %s failed: %s", name, e)

        rec = HealingRecord(module_path, error_type, error_msg,
                            "all_failed", False, "no strategy worked")
        self._history.append(rec)
        return False

    # ── Стратегии исцеления ──────────────────────────────
    def _strategy_syntax_fix(self, file_path: str, error_type: str,
                             error_msg: str) -> Tuple[bool, str]:
        """Исправляет синтаксические ошибки."""
        if error_type != "SyntaxError":
            return (False, "not a syntax error")

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Пытаемся спарсить — если OK, ошибка не в синтаксисе
        try:
            ast.parse(source)
            return (False, "source parses OK, error elsewhere")
        except SyntaxError as se:
            pass

        fixed = source
        fixes_applied = []

        # Fix 1: незакрытые скобки
        open_parens = fixed.count("(") - fixed.count(")")
        if open_parens > 0:
            fixed += ")" * open_parens
            fixes_applied.append(f"+{open_parens} closing parens")

        open_brackets = fixed.count("[") - fixed.count("]")
        if open_brackets > 0:
            fixed += "]" * open_brackets
            fixes_applied.append(f"+{open_brackets} closing brackets")

        # Fix 2: отступ (TabError) → заменяем табы на пробелы
        if "\t" in fixed:
            fixed = fixed.replace("\t", "    ")
            fixes_applied.append("tabs→spaces")

        # Fix 3: trailing colon без тела → добавляем pass
        lines = fixed.split("\n")
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            if line.rstrip().endswith(":"):
                # Проверяем, есть ли следующая строка с отступом
                next_indent = None
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if next_line.strip() == "" or \
                       (not next_line.startswith(" ") and not next_line.startswith("\t")):
                        curr_indent = len(line) - len(line.lstrip())
                        new_lines.append(" " * (curr_indent + 4) + "pass")
                        fixes_applied.append(f"added pass after line {i+1}")
        if fixes_applied:
            fixed = "\n".join(new_lines) if new_lines != lines else fixed

        # Validate fix
        try:
            ast.parse(fixed)
        except SyntaxError:
            return (False, "auto-fix failed to resolve syntax")

        # Save
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(fixed)

        return (True, "; ".join(fixes_applied))

    def _strategy_import_fix(self, file_path: str, error_type: str,
                             error_msg: str) -> Tuple[bool, str]:
        """Исправляет ImportError: оборачивает проблемный import в try/except."""
        if error_type not in ("ImportError", "ModuleNotFoundError"):
            return (False, "not an import error")

        # Извлекаем имя модуля из ошибки
        match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_msg)
        if not match:
            match = re.search(r"cannot import name ['\"]([^'\"]+)['\"]", error_msg)
        if not match:
            return (False, "cannot extract module name")

        bad_module = match.group(1)

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Ищем строку import
        pattern = re.compile(
            rf"^((?:from\s+\S*{re.escape(bad_module)}\S*\s+import\s+.+)|"
            rf"(?:import\s+\S*{re.escape(bad_module)}\S*.*))$",
            re.MULTILINE
        )
        m = pattern.search(source)
        if not m:
            return (False, f"import line for '{bad_module}' not found")

        old_line = m.group(0)
        indent = len(old_line) - len(old_line.lstrip())
        pad = " " * indent

        new_block = (
            f"{pad}try:\n"
            f"{pad}    {old_line.strip()}\n"
            f"{pad}except ImportError:\n"
            f"{pad}    {bad_module.split('.')[-1]} = None  # self-healing fallback"
        )

        patched = source.replace(old_line, new_block, 1)

        # Validate
        try:
            ast.parse(patched)
        except SyntaxError:
            return (False, "patched code has syntax error")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(patched)

        return (True, f"wrapped import {bad_module} in try/except")

    def _strategy_runtime_patch(self, file_path: str, error_type: str,
                                error_msg: str) -> Tuple[bool, str]:
        """
        Runtime-патч: если ошибка в конкретной строке,
        оборачиваем блок в try/except с логированием.
        """
        if error_type in ("SyntaxError", "ImportError", "ModuleNotFoundError"):
            return (False, "handled by other strategies")

        # Пытаемся найти номер строки
        line_match = re.search(r"line (\d+)", error_msg)
        if not line_match:
            return (False, "cannot determine error line")

        err_line = int(line_match.group(1))

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if err_line < 1 or err_line > len(lines):
            return (False, f"line {err_line} out of range")

        target = lines[err_line - 1]
        indent = len(target) - len(target.lstrip())
        pad = " " * indent

        # Оборачиваем блок (текущую + 2 след. строки) в try/except
        end = min(err_line + 2, len(lines))
        block_lines = lines[err_line - 1:end]

        try_block = [f"{pad}try:\n"]
        for bl in block_lines:
            try_block.append(f"{pad}    {bl.lstrip()}")
        try_block.append(f"{pad}except Exception as _heal_e:\n")
        try_block.append(f"{pad}    pass  # self-healing: {error_type}\n")

        new_lines = lines[:err_line - 1] + try_block + lines[end:]
        patched = "".join(new_lines)

        try:
            ast.parse(patched)
        except SyntaxError:
            return (False, "runtime patch created syntax error")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(patched)

        return (True, f"wrapped lines {err_line}-{end} in try/except")

    # ── Утилиты ──────────────────────────────────────────
    def _resolve_file(self, module_path: str) -> Optional[str]:
        """Преобразует module.path в filesystem path."""
        # уже путь к файлу?
        if os.path.isfile(module_path):
            return module_path
        # module dot notation → path
        candidate = module_path.replace(".", os.sep) + ".py"
        if os.path.isfile(candidate):
            return candidate
        # src/ prefix
        candidate2 = os.path.join("src", candidate)
        if os.path.isfile(candidate2):
            return candidate2
        return None

    def _backup(self, file_path: str) -> None:
        """Создаёт backup файла перед патчем."""
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            name = Path(file_path).name
            backup = os.path.join(self.BACKUP_DIR, f"{name}.{ts}.bak")
            with open(file_path, "r", encoding="utf-8") as src:
                content = src.read()
            with open(backup, "w", encoding="utf-8") as dst:
                dst.write(content)
            log.info("Healing backup: %s", backup)
        except Exception as e:
            log.warning("Healing backup failed: %s", e)

    def _try_hot_reload(self, module_path: str) -> None:
        """Пытается перезагрузить модуль после патча."""
        mod_name = module_path.replace("/", ".").replace("\\", ".").rstrip(".py")
        if mod_name.endswith(".py"):
            mod_name = mod_name[:-3]
        mod = sys.modules.get(mod_name)
        if mod:
            try:
                importlib.reload(mod)
                log.info("Healing: hot-reload %s OK", mod_name)
            except Exception as e:
                log.warning("Healing: hot-reload %s failed: %s", mod_name, e)

    @staticmethod
    def _extract_module_from_tb(exc_tb) -> Optional[str]:
        """Извлекает имя модуля из traceback."""
        if exc_tb is None:
            return None
        # идём к самому глубокому фрейму
        tb = exc_tb
        while tb.tb_next:
            tb = tb.tb_next
        filename = tb.tb_frame.f_code.co_filename
        if filename and "src" in filename:
            return filename
        return filename

    # ── Валидация файла ──────────────────────────────────
    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """Проверяет синтаксис Python-файла."""
        if not os.path.isfile(file_path):
            return (False, f"файл не найден: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source)
            return (True, "✅ Синтаксис OK")
        except SyntaxError as e:
            return (False, f"❌ SyntaxError: {e}")

    def validate_all_src(self) -> str:
        """Валидирует все .py файлы в src/."""
        results = []
        ok_count = 0
        fail_count = 0
        for root, _, files in os.walk("src"):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fp = os.path.join(root, fname)
                valid, msg = self.validate_file(fp)
                if valid:
                    ok_count += 1
                else:
                    fail_count += 1
                    results.append(f"  ❌ {fp}: {msg}")
        header = f"🩹 ВАЛИДАЦИЯ КОДА: {ok_count} ✅ / {fail_count} ❌"
        if results:
            return header + "\n" + "\n".join(results)
        return header + "\n  Все файлы валидны."

    # ── Статус ───────────────────────────────────────────
    def status(self) -> str:
        with self._lock:
            total = len(self._history)
            success = sum(1 for r in self._history if r.success)
            failed = total - success
        lines = [
            "🩹 SELF-HEALING ENGINE",
            f"  Версия: {self.VERSION} | Enabled: {self._enabled}",
            f"  Intercepting: {self._intercepting}",
            f"  Исцелений: {total} (✅ {success} / ❌ {failed})",
        ]
        # последние 5
        with self._lock:
            recent = self._history[-5:]
        if recent:
            lines.append("  Последние:")
            for r in recent:
                ts = time.strftime("%H:%M:%S", time.localtime(r.ts))
                icon = "✅" if r.success else "❌"
                lines.append(f"    {icon} [{ts}] {r.module} via {r.strategy}: {r.patch_summary[:50]}")
        return "\n".join(lines)

    def history_json(self) -> str:
        with self._lock:
            data = [r.to_dict() for r in self._history[-50:]]
        return json.dumps(data, ensure_ascii=False, indent=2)
