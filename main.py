"""
main.py — Оркестратор Argos Universal OS v1.3
Запуск: python main.py [--no-gui] [--mobile] [--dashboard] [--wake] [--root]
"""

import sys
import os
import argparse
import asyncio
import threading
import logging

# ─── Bootstrap: загрузка .env ────────────────────────────────────────────────
def _load_env() -> None:
    """Ищет .env в CWD, затем в корне репозитория."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    cwd_env = os.path.join(os.getcwd(), ".env")
    repo_env = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(cwd_env):
        load_dotenv(cwd_env, override=False)
    elif os.path.exists(repo_env):
        load_dotenv(repo_env, override=False)

_load_env()

# ─── Логгер ──────────────────────────────────────────────────────────────────
try:
    from src.argos_logger import get_logger
    log = get_logger("main")
except Exception:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("main")


# ─── Аргументы CLI ───────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Argos Universal OS v1.3",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--no-gui",    action="store_true", help="Headless-режим (без GUI)")
    p.add_argument("--mobile",    action="store_true", help="Android/Kivy UI")
    p.add_argument("--dashboard", action="store_true", help="Запустить веб-панель :8080")
    p.add_argument("--wake",      action="store_true", help='Wake Word "Аргос"')
    p.add_argument("--root",      action="store_true", help="Запросить права администратора")
    return p.parse_args()


# ─── Вспомогательные функции старта подсистем ────────────────────────────────
def _safe_import(module_path: str, attr: str = None):
    """Импортирует модуль или атрибут; при ошибке возвращает None и логирует."""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, attr) if attr else mod
    except Exception as exc:
        log.warning("Не удалось загрузить %s: %s", module_path, exc)
        return None


def _start_background(fn, name: str, *args, **kwargs) -> threading.Thread | None:
    """Запускает функцию в daemon-потоке."""
    try:
        t = threading.Thread(target=fn, args=args, kwargs=kwargs,
                             name=name, daemon=True)
        t.start()
        log.info("▶ %s запущен", name)
        return t
    except Exception as exc:
        log.error("Ошибка запуска %s: %s", name, exc)
        return None


# ─── Инициализация БД ─────────────────────────────────────────────────────────
def init_database() -> None:
    db_init = _safe_import("db_init")
    if db_init and hasattr(db_init, "init_db"):
        try:
            db_init.init_db()
            log.info("✅ SQLite инициализирована")
        except Exception as exc:
            log.error("Ошибка инициализации БД: %s", exc)


# ─── Ядро (Core) ──────────────────────────────────────────────────────────────
def load_core():
    Core = _safe_import("src.core", "ArgosCore")
    if Core is None:
        log.critical("src.core не найден — невозможно запустить Argos")
        sys.exit(1)
    try:
        core = Core()
        log.info("✅ ArgosCore загружен")
        return core
    except Exception as exc:
        log.critical("Ошибка инициализации ArgosCore: %s", exc)
        sys.exit(1)


# ─── AWA-Core ─────────────────────────────────────────────────────────────────
def start_awa(core) -> None:
    AWACore = _safe_import("src.awa_core", "AWACore")
    if AWACore:
        try:
            awa = AWACore(core)
            awa.start()
            log.info("✅ AWA-Core запущен")
        except Exception as exc:
            log.warning("AWA-Core: %s", exc)


# ─── Task Queue ───────────────────────────────────────────────────────────────
def start_task_queue(core) -> None:
    TaskQueue = _safe_import("src.task_queue", "TaskQueue")
    if TaskQueue:
        try:
            workers = int(os.getenv("ARGOS_TASK_WORKERS", "2"))
            tq = TaskQueue(core, workers=workers)
            tq.start()
            log.info("✅ TaskQueue запущен (%d workers)", workers)
        except Exception as exc:
            log.warning("TaskQueue: %s", exc)


# ─── Hardware Guard (гомеостаз) ───────────────────────────────────────────────
def start_hardware_guard(core) -> None:
    if os.getenv("ARGOS_HOMEOSTASIS", "on").lower() != "on":
        return
    HardwareGuard = _safe_import("src.hardware_guard", "HardwareGuard")
    if HardwareGuard:
        try:
            interval = int(os.getenv("ARGOS_HOMEOSTASIS_INTERVAL", "8"))
            hg = HardwareGuard(core, interval=interval)
            _start_background(hg.run, "HardwareGuard")
        except Exception as exc:
            log.warning("HardwareGuard: %s", exc)


# ─── Self-Healing Engine ──────────────────────────────────────────────────────
def start_self_healing(core) -> None:
    SelfHealing = _safe_import("src.self_healing", "SelfHealingEngine")
    if SelfHealing:
        try:
            sh = SelfHealing(core)
            sh.start()
            log.info("✅ SelfHealingEngine запущен")
        except Exception as exc:
            log.warning("SelfHealingEngine: %s", exc)


# ─── Adaptive Drafter (TLT) ───────────────────────────────────────────────────
def start_adaptive_drafter(core) -> None:
    AdaptiveDrafter = _safe_import("src.adaptive_drafter", "AdaptiveDrafter")
    if AdaptiveDrafter:
        try:
            ad = AdaptiveDrafter(core)
            ad.start()
            log.info("✅ AdaptiveDrafter запущен")
        except Exception as exc:
            log.warning("AdaptiveDrafter: %s", exc)


# ─── P2P Bridge ───────────────────────────────────────────────────────────────
def start_p2p(core) -> None:
    P2PBridge = _safe_import("src.connectivity.p2p_bridge", "P2PBridge")
    if P2PBridge:
        try:
            p2p = P2PBridge(core)
            _start_background(p2p.run, "P2PBridge")
        except Exception as exc:
            log.warning("P2PBridge: %s", exc)


# ─── Telegram Bot ─────────────────────────────────────────────────────────────
def start_telegram(core) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        log.info("ℹ️  TELEGRAM_BOT_TOKEN не задан — Telegram-бот отключён")
        return
    TelegramBot = _safe_import("src.connectivity.telegram_bot", "TelegramBot")
    if TelegramBot:
        try:
            bot = TelegramBot(core)
            _start_background(bot.run, "TelegramBot")
        except Exception as exc:
            log.warning("TelegramBot: %s", exc)


# ─── Alert System ─────────────────────────────────────────────────────────────
def start_alerts(core) -> None:
    AlertSystem = _safe_import("src.connectivity.alert_system", "AlertSystem")
    if AlertSystem:
        try:
            al = AlertSystem(core)
            _start_background(al.run, "AlertSystem")
        except Exception as exc:
            log.warning("AlertSystem: %s", exc)


# ─── IoT Bridge ───────────────────────────────────────────────────────────────
def start_iot(core) -> None:
    IoTBridge = _safe_import("src.connectivity.iot_bridge", "IoTBridge")
    if IoTBridge:
        try:
            iot = IoTBridge(core)
            _start_background(iot.run, "IoTBridge")
        except Exception as exc:
            log.warning("IoTBridge: %s", exc)


# ─── Curiosity (автономное любопытство) ───────────────────────────────────────
def start_curiosity(core) -> None:
    if os.getenv("ARGOS_CURIOSITY", "on").lower() != "on":
        return
    Curiosity = _safe_import("src.curiosity", "CuriosityEngine")
    if Curiosity:
        try:
            idle = int(os.getenv("ARGOS_CURIOSITY_IDLE_SEC", "600"))
            cur = Curiosity(core, idle_sec=idle)
            _start_background(cur.run, "CuriosityEngine")
        except Exception as exc:
            log.warning("CuriosityEngine: %s", exc)


# ─── Skill Loader ─────────────────────────────────────────────────────────────
def load_skills(core) -> None:
    SkillLoader = _safe_import("src.skill_loader", "SkillLoader")
    if SkillLoader:
        try:
            sl = SkillLoader(core)
            sl.load_all()
            log.info("✅ Skills загружены")
        except Exception as exc:
            log.warning("SkillLoader: %s", exc)


# ─── Root-привилегии ──────────────────────────────────────────────────────────
def request_root() -> None:
    root_manager = _safe_import("src.security.root_manager")
    if root_manager and hasattr(root_manager, "request_root"):
        try:
            root_manager.request_root()
            log.info("✅ Права администратора получены")
        except Exception as exc:
            log.warning("root_manager: %s", exc)


# ─── Wake Word ────────────────────────────────────────────────────────────────
def start_wake_word(core) -> None:
    WakeWord = _safe_import("src.connectivity.wake_word", "WakeWordListener")
    if WakeWord:
        try:
            ww = WakeWord(core)
            _start_background(ww.run, "WakeWordListener")
        except Exception as exc:
            log.warning("WakeWordListener: %s", exc)


# ─── Web Dashboard ────────────────────────────────────────────────────────────
def start_dashboard(core) -> None:
    WebDashboard = _safe_import("src.interface.web_dashboard", "WebDashboard")
    if WebDashboard:
        try:
            wd = WebDashboard(core)
            _start_background(wd.run, "WebDashboard")
            log.info("✅ Dashboard запущен на http://localhost:8080")
        except Exception as exc:
            log.warning("WebDashboard: %s", exc)


# ─── GUI ──────────────────────────────────────────────────────────────────────
def start_gui(core) -> None:
    GUI = _safe_import("src.interface.gui", "ArgosGUI")
    if GUI is None:
        log.warning("GUI недоступен, переключаюсь в headless-режим")
        run_headless(core)
        return
    try:
        gui = GUI(core)
        log.info("✅ Desktop GUI запускается…")
        gui.run()          # блокирующий вызов (mainloop)
    except Exception as exc:
        log.error("Ошибка GUI: %s", exc)
        run_headless(core)


def start_mobile_ui(core) -> None:
    MobileUI = _safe_import("src.interface.mobile_ui", "MobileUI")
    if MobileUI is None:
        log.warning("MobileUI недоступен")
        run_headless(core)
        return
    try:
        ui = MobileUI(core)
        log.info("✅ Mobile UI запускается…")
        ui.run()
    except Exception as exc:
        log.error("Ошибка MobileUI: %s", exc)
        run_headless(core)


# ─── Headless-режим (REPL) ────────────────────────────────────────────────────
def run_headless(core) -> None:
    log.info("🖥️  Headless-режим. Введите команду (exit — выход).")
    print("\n" + "─" * 50)
    print("  👁️  ARGOS UNIVERSAL OS v1.3  |  headless")
    print("─" * 50)
    while True:
        try:
            user_input = input("\n▶ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👁️ Аргос завершает работу.")
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "выход"}:
            print("👁️ До свидания.")
            break
        try:
            response = core.process(user_input)
            print(f"\n{response}")
        except Exception as exc:
            log.error("Ошибка обработки команды: %s", exc)


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main() -> None:
    args = parse_args()

    log.info("=" * 60)
    log.info("  👁️  ARGOS UNIVERSAL OS v1.3 — старт")
    log.info("=" * 60)

    # Права администратора (если запрошено)
    if args.root:
        request_root()

    # БД
    init_database()

    # Ядро
    core = load_core()

    # Фоновые подсистемы
    start_awa(core)
    start_task_queue(core)
    start_self_healing(core)
    start_adaptive_drafter(core)
    start_hardware_guard(core)
    start_alerts(core)
    start_iot(core)
    start_p2p(core)
    start_telegram(core)
    start_curiosity(core)
    load_skills(core)

    # Опциональные подсистемы
    if args.wake:
        start_wake_word(core)
    if args.dashboard:
        start_dashboard(core)

    # Интерфейс (блокирующий вызов — всегда последним)
    if args.mobile:
        start_mobile_ui(core)
    elif args.no_gui:
        run_headless(core)
    else:
        start_gui(core)


if __name__ == "__main__":
    main()
