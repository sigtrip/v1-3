"""
vad_events.py — Модуль подписки на события VAD (начало/конец речи)
Может использоваться в GUI, web, Telegram, CLI.
"""
from src.connectivity.event_bus import bus
from src.argos_logger import get_logger

log = get_logger("vad.events")

# Подписчик на события VAD

def on_vad_event(ev):
    if ev.type == "vad.speech_start":
        log.info(f"VAD: Начало речи ({ev.payload})")
        # Здесь можно добавить интеграцию с GUI/web (например, показать индикатор)
    elif ev.type == "vad.speech_end":
        log.info(f"VAD: Конец речи ({ev.payload})")
        # Здесь можно скрыть индикатор или отправить событие в интерфейс

bus.subscribe("vad.speech_start", on_vad_event)
bus.subscribe("vad.speech_end", on_vad_event)

# Пример: интеграция с внешним интерфейсом
# def on_vad_event(ev):
#     if ev.type == "vad.speech_start":
#         gui.show_vad_indicator()
#     elif ev.type == "vad.speech_end":
#         gui.hide_vad_indicator()
# bus.subscribe("vad.speech_start", on_vad_event)
# bus.subscribe("vad.speech_end", on_vad_event)
