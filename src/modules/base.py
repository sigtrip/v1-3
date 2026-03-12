"""base.py — Базовый класс модуля Аргоса"""
from __future__ import annotations
from abc import ABC, abstractmethod

class BaseModule(ABC):
    module_id: str = "base"
    title: str = "Base Module"

    def setup(self, core) -> None:
        self.core = core

    @abstractmethod
    def can_handle(self, text: str, lower: str) -> bool: ...

    @abstractmethod
    def handle(self, text: str, lower: str, **kwargs) -> str | None: ...
