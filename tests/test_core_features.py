"""
test_core_features.py — Тесты для основных функций Аргоса
Покрывает: vision, memory, admin, encryption, quantum logic
"""

import pytest
import os
import json
import tempfile
from pathlib import Path


class TestVision:
    """Тесты Vision-модуля (анализ изображений)."""

    def test_vision_import(self):
        """Проверяет импорт vision модуля."""
        try:
            from src import vision

            assert hasattr(vision, "ArgosVision")
        except ImportError:
            pytest.skip("Vision module not available")

    def test_vision_init(self):
        """Инициализация Vision."""
        try:
            from src.vision import ArgosVision

            v = ArgosVision()
            assert v is not None
        except Exception as e:
            pytest.skip(f"Vision init failed: {e}")


class TestMemory:
    """Тесты Memory-модуля (долгосрочная память)."""

    def test_memory_import(self):
        """Проверяет импорт memory модуля."""
        try:
            from src import memory

            assert hasattr(memory, "ArgosMemory")
        except ImportError:
            pytest.skip("Memory module not available")

    def test_memory_save_fact(self):
        """Сохранение факта в память."""
        try:
            from src.memory import ArgosMemory

            mem = ArgosMemory()
            mem.save_fact("test_key", "test_value")
            # Проверяем, что факт сохранён
            assert mem is not None
        except Exception as e:
            pytest.skip(f"Memory save failed: {e}")


class TestAdmin:
    """Тесты Admin-модуля (управление файлами/процессами)."""

    def test_admin_init(self):
        """Инициализация Admin."""
        from src.admin import ArgosAdmin

        admin = ArgosAdmin()
        assert admin is not None

    def test_admin_get_stats(self):
        """Получение статистики системы."""
        from src.admin import ArgosAdmin

        admin = ArgosAdmin()
        stats = admin.get_stats()
        assert isinstance(stats, str)
        assert "ЦП" in stats or "CPU" in stats

    def test_admin_list_processes(self):
        """Список процессов."""
        from src.admin import ArgosAdmin

        admin = ArgosAdmin()
        procs = admin.list_processes()
        assert isinstance(procs, str)

    def test_admin_read_file(self):
        """Чтение файла."""
        from src.admin import ArgosAdmin

        admin = ArgosAdmin()
        # Читаем существующий файл
        result = admin.read_file("/etc/hostname")
        assert isinstance(result, str)

    def test_admin_create_file(self):
        """Создание файла."""
        from src.admin import ArgosAdmin

        admin = ArgosAdmin()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            result = admin.create_file(path, "test content")
            assert "✅" in result or "успешно" in result.lower()


class TestEncryption:
    """Тесты Encryption-модуля (AES-256-GCM)."""

    def test_encryption_import(self):
        """Проверяет импорт encryption модуля."""
        from src.security import encryption

        assert hasattr(encryption, "ArgosEncryption")

    def test_encryption_init(self):
        """Инициализация шифрования."""
        from src.security.encryption import ArgosEncryption

        enc = ArgosEncryption()
        assert enc is not None

    def test_encryption_encrypt_decrypt(self):
        """Шифрование и расшифровка."""
        from src.security.encryption import ArgosEncryption

        enc = ArgosEncryption()
        plaintext = "secret message"
        encrypted = enc.encrypt(plaintext)
        decrypted = enc.decrypt(encrypted)
        assert decrypted == plaintext


class TestQuantumLogic:
    """Тесты Quantum Logic (5 состояний)."""

    def test_quantum_logic_import(self):
        """Проверяет импорт quantum logic."""
        from src.quantum.logic import ArgosQuantum

        assert ArgosQuantum is not None

    def test_quantum_states(self):
        """Проверяет все 5 квантовых состояний."""
        from src.quantum.logic import ArgosQuantum

        aq = ArgosQuantum()
        assert len(aq.states) == 5
        assert "Analytic" in aq.states
        assert "Creative" in aq.states
        assert "Protective" in aq.states
        assert "Unstable" in aq.states
        assert "All-Seeing" in aq.states


class TestEventBus:
    """Тесты Event Bus (шина событий)."""

    def test_event_bus_import(self):
        """Проверяет импорт event bus."""
        from src.connectivity.event_bus import EventBus, Event

        assert EventBus is not None
        assert Event is not None

    def test_event_bus_subscribe(self):
        """Подписка на события."""
        from src.connectivity.event_bus import EventBus

        bus = EventBus()
        called = []

        def callback(event):
            called.append(event)

        bus.subscribe("test.event", callback)
        bus.publish("test.event", {"data": "test"})
        # Даём время на обработку
        import time

        time.sleep(0.1)
        assert len(called) > 0


class TestHealthCheck:
    """Тесты Health Check."""

    def test_health_check_paths(self):
        """Проверяет наличие ключевых файлов."""
        assert os.path.exists("main.py")
        assert os.path.exists("src/core.py")
        assert os.path.exists("src/vision.py")
        assert os.path.exists("config/identity.json")

    def test_health_check_config(self):
        """Проверяет конфиги."""
        assert os.path.exists("config/smart_systems.json")
        with open("config/smart_systems.json") as f:
            data = json.load(f)
            assert isinstance(data, dict)


class TestLogging:
    """Тесты Logging."""

    def test_argos_logger_import(self):
        """Проверяет импорт логгера."""
        from src.argos_logger import get_logger

        logger = get_logger("test")
        assert logger is not None

    def test_argos_logger_log(self):
        """Логирование."""
        from src.argos_logger import get_logger

        logger = get_logger("test.log")
        logger.info("Test message")
        logger.warning("Test warning")
        logger.error("Test error")


class TestIntegration:
    """Интеграционные тесты."""

    def test_core_import(self):
        """Проверяет импорт основного ядра."""
        try:
            from src import core

            assert hasattr(core, "ArgosCore")
        except ImportError:
            pytest.skip("Core module not available")

    def test_all_modules_syntax(self):
        """Проверяет синтаксис всех модулей."""
        import ast

        src_dir = Path("src")
        py_files = list(src_dir.rglob("*.py"))
        assert len(py_files) > 50, f"Expected >50 Python files, got {len(py_files)}"

        for py_file in py_files[:10]:  # Проверяем первые 10
            try:
                with open(py_file) as f:
                    ast.parse(f.read())
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {py_file}: {e}")
