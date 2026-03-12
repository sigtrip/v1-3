"""
main.py — Оркестратор Argos Universal OS v1.3
Запуск: python main.py [--no-gui]
"""
import sys, os, argparse, logging

def _load_env():
    try:
        from dotenv import load_dotenv
        for p in [".env", os.path.join(os.path.dirname(__file__), ".env")]:
            if os.path.exists(p):
                load_dotenv(p, override=False)
                break
    except ImportError:
        pass

_load_env()

try:
    from src.argos_logger import get_logger
    log = get_logger("main")
except Exception:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    log = logging.getLogger("main")

def parse_args():
    p = argparse.ArgumentParser(description="Argos Universal OS v1.3")
    p.add_argument("--no-gui", action="store_true")
    p.add_argument("--dashboard", action="store_true")
    return p.parse_args()

def run_terminal(core):
    """REPL терминал."""
    print("\n--- ARGOS UNIVERSAL OS ORCHESTRATOR TERMINAL ---")
    print("Initialization in progress... Once you see the \'▶\' prompt, you can type commands.\n")

    import psutil
    from datetime import datetime
    from src.quantum.logic import STATES

    q = core.quantum.generate_state() if core.quantum else {"name": "System"}
    print(f"🔱 ARGOS UNIVERSAL OS v{core.VERSION}")
    print("━" * 50)
    print(f"[BOOT] ArgosCore engine...                    ✅")
    print(f"[BOOT] QuantumEngine...                       ✅  состояние: {q['name']}")
    print(f"[BOOT] Memory...                              {'✅' if core.memory else '⚠️'}")
    print(f"[BOOT] GitOps...                              {'✅' if core.git_ops else '⚠️'}")
    print(f"[BOOT] Собственная ML-модель...               {'✅' if core.own_model else '⚠️'}")
    print(f"[BOOT] Curiosity...                           {'✅' if core.curiosity else '⚠️'}")
    print(f"[BOOT] Homeostasis...                         {'✅' if core.homeostasis else '⚠️'}")
    print("━" * 50)
    print(f"⚛️  Квантовое состояние : {q['name']}")
    print(f"🧠 Версия              : {core.VERSION}")
    print(f"🕐 Время               : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("━" * 50)
    print("Система готова. Введи \'помощь\' для списка команд.\n")

    while True:
        try:
            user_input = input("▶ ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "выход", "quit"]:
                print("🔱 Аргос: завершение работы.")
                break
            result = core.process(user_input)
            answer = result.get("answer", "") if isinstance(result, dict) else str(result)
            print(f"\n{answer}\n")
        except KeyboardInterrupt:
            print("\n🔱 Аргос: Ctrl+C получен. Завершение.")
            break
        except EOFError:
            print("\n⚠️  Non-interactive mode. Запусти с флагом --no-gui или в интерактивной среде.")
            break

if __name__ == "__main__":
    args = parse_args()
    log.info("Запуск Argos Universal OS v1.3...")

    try:
        from src.core import ArgosCore
        core = ArgosCore()
    except Exception as e:
        log.critical("Не удалось загрузить ArgosCore: %s", e)
        sys.exit(1)

    run_terminal(core)
