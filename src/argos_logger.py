"""
argos_logger.py — Централизованный логгер Аргоса
  Пишет в файл + консоль. Ротация по размеру 5MB.
  Используется во всех модулях вместо print().
"""
import logging
import os
import re
from logging.handlers import RotatingFileHandler

os.makedirs("logs", exist_ok=True)


class _SensitiveDataFilter(logging.Filter):
    _TG_TOKEN_RE = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b")

    @classmethod
    def _sanitize(cls, value):
        if isinstance(value, str):
            return cls._TG_TOKEN_RE.sub("***REDACTED***", value)
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize(v) for k, v in record.args.items()}
            else:
                record.args = tuple(self._sanitize(v) for v in record.args)
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_info = (
                record.exc_info[0],
                type(record.exc_info[1])(self._sanitize(str(record.exc_info[1]))),
                record.exc_info[2],
            )
        return True

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

    scrub = _SensitiveDataFilter()
    fh.addFilter(scrub)
    ch.addFilter(scrub)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

# Глобальный логгер
log = get_logger("argos.core")

# README alias
setup_logging = get_logger
ArgosLogger = type("ArgosLogger", (), {"get": staticmethod(get_logger)})
