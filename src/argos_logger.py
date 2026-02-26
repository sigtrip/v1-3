"""
argos_logger.py — Централизованный логгер Аргоса
  Пишет в файл + консоль. Ротация по размеру 5MB.
  Используется во всех модулях вместо print().
"""
import logging
import os
from logging.handlers import RotatingFileHandler

os.makedirs("logs", exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Уже инициализирован

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)-20s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Файл — ротация 5MB, 3 бэкапа
    fh = RotatingFileHandler(
        "logs/argos.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Консоль — только INFO+
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

# Глобальный логгер
log = get_logger("argos.core")
