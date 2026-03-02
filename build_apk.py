"""
build_apk.py — Сборка Argos Universal OS в Android APK
  Использует Buildozer (Kivy) для упаковки проекта.

  Запуск:
    python build_apk.py                # debug APK
    python build_apk.py --release      # release APK (нужен keystore)
    python build_apk.py --clean        # очистить кэш и пересобрать
    python build_apk.py --aab          # Android App Bundle (для Google Play)

  Требования:
    pip install buildozer
    Java JDK 17+, Android SDK/NDK (buildozer скачает автоматически)
"""
import os
import sys
import subprocess
import shutil
import importlib.util
from pathlib import Path


# ─── Конфигурация ────────────────────────────────────────────────
SPEC_FILE = "buildozer.spec"
APK_SEARCH_DIRS = ["bin", "dist", "build"]
APK_PATTERNS = ["*.apk", "**/*.apk"]
AAB_PATTERNS = ["*.aab", "**/*.aab"]


def _find_artifact(patterns: list[str]) -> Path | None:
    """Ищет самый свежий артефакт сборки."""
    candidates = []
    for search_dir in APK_SEARCH_DIRS:
        base = Path(search_dir)
        if not base.exists():
            continue
        for pattern in patterns:
            candidates.extend(base.glob(pattern))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _check_java() -> bool:
    """Проверяет наличие Java JDK."""
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True, text=True, timeout=10
        )
        version_line = (result.stderr or result.stdout).split("\n")[0]
        print(f"[APK BUILD]: Java: {version_line}")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _ensure_buildozer():
    """Устанавливает buildozer если его нет."""
    if importlib.util.find_spec("buildozer") is None:
        print("[APK BUILD]: Устанавливаю buildozer...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "buildozer"],
            stdout=subprocess.DEVNULL
        )
        print("[APK BUILD]: buildozer установлен ✓")
    else:
        print("[APK BUILD]: buildozer найден ✓")


def _ensure_deps():
    """Проверяет системные зависимости для buildozer."""
    # На Linux нужны определённые пакеты
    if sys.platform.startswith("linux"):
        deps = [
            "git", "zip", "unzip", "openjdk-17-jdk",
            "autoconf", "libtool", "pkg-config",
            "zlib1g-dev", "libncurses5-dev", "libncursesw5-dev",
            "libtinfo5", "cmake", "libffi-dev", "libssl-dev",
        ]
        missing = []
        for dep in deps:
            ret = subprocess.run(
                ["dpkg", "-s", dep],
                capture_output=True, timeout=5
            )
            if ret.returncode != 0:
                missing.append(dep)

        if missing:
            print(f"[APK BUILD]: Недостающие пакеты: {', '.join(missing)}")
            print(f"[APK BUILD]: sudo apt install -y {' '.join(missing)}")
            # Пробуем установить автоматически
            try:
                subprocess.run(
                    ["sudo", "apt", "install", "-y"] + missing,
                    check=True, timeout=300
                )
                print("[APK BUILD]: Системные зависимости установлены ✓")
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("[APK BUILD]: ⚠️  Не удалось установить зависимости автоматически.")
                print("[APK BUILD]:    Установите вручную и перезапустите сборку.")


def build():
    """Основная функция сборки APK."""
    print("=" * 50)
    print("  ARGOS APK BUILD")
    print("=" * 50)

    # ── Проверки ──────────────────────────────────────────────
    if not os.path.exists(SPEC_FILE):
        print(f"[APK BUILD]: ❌ Не найден {SPEC_FILE}")
        print(f"[APK BUILD]:    Запустите из корня проекта Argos.")
        sys.exit(1)

    # Java
    if not _check_java():
        print("[APK BUILD]: ⚠️  Java не найдена. Buildozer попробует скачать JDK.")

    # Buildozer
    _ensure_buildozer()

    # Системные зависимости (Linux)
    _ensure_deps()

    # ── Определяем режим сборки ───────────────────────────────
    clean = "--clean" in sys.argv
    release = "--release" in sys.argv
    aab = "--aab" in sys.argv

    # ── Очистка (если запрошена) ──────────────────────────────
    if clean:
        print("[APK BUILD]: Очистка предыдущей сборки...")
        for d in [".buildozer", "bin"]:
            if os.path.isdir(d):
                shutil.rmtree(d)
                print(f"  ✓ Удалён {d}/")

    # ── Формируем команду ─────────────────────────────────────
    cmd = [sys.executable, "-m", "buildozer", "-v"]

    if aab:
        target = "android release" if release else "android debug"
        # AAB генерируется при release
        cmd.extend(target.split())
    elif release:
        cmd.extend(["android", "release"])
    else:
        cmd.extend(["android", "debug"])

    print(f"\n[APK BUILD]: Команда: {' '.join(cmd)}")
    print("[APK BUILD]: Это может занять 10-30 минут при первой сборке...\n")

    # ── Запуск ────────────────────────────────────────────────
    try:
        result = subprocess.run(cmd, timeout=1800)  # 30 мин таймаут
    except subprocess.TimeoutExpired:
        print("\n[APK BUILD]: ❌ Таймаут сборки (30 мин)")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[APK BUILD]: Сборка прервана пользователем.")
        sys.exit(1)

    if result.returncode != 0:
        print(f"\n[APK BUILD]: ❌ Buildozer завершился с кодом {result.returncode}")
        print("[APK BUILD]: Проверьте логи выше для деталей.")
        sys.exit(1)

    # ── Ищем артефакт ─────────────────────────────────────────
    patterns = AAB_PATTERNS if aab else APK_PATTERNS
    artifact = _find_artifact(patterns)

    if artifact:
        size_mb = artifact.stat().st_size / (1024 * 1024)
        ext = artifact.suffix.upper().lstrip(".")
        print(f"\n{'=' * 50}")
        print(f"  ✅ {ext} СОБРАН УСПЕШНО")
        print(f"  Файл: {artifact}")
        print(f"  Размер: {size_mb:.1f} MB")
        print(f"{'=' * 50}")

        # Копируем в builds/ для удобства
        builds_dir = Path("builds")
        builds_dir.mkdir(exist_ok=True)
        dest = builds_dir / artifact.name
        shutil.copy2(artifact, dest)
        print(f"  Копия: {dest}")

        if not aab:
            print(f"\n  Установка на устройство:")
            print(f"    adb install -r {artifact}")
    else:
        print(f"\n[APK BUILD]: ⚠️  Сборка завершена, но артефакт не найден.")
        print(f"[APK BUILD]:    Проверьте директории: {', '.join(APK_SEARCH_DIRS)}")
        sys.exit(1)


def deploy():
    """Установка APK на подключённое устройство через ADB."""
    apk = _find_artifact(APK_PATTERNS)
    if not apk:
        print("[APK DEPLOY]: ❌ APK не найден. Сначала соберите: python build_apk.py")
        sys.exit(1)

    print(f"[APK DEPLOY]: Устанавливаю {apk}...")
    try:
        subprocess.run(["adb", "install", "-r", str(apk)], check=True, timeout=120)
        print("[APK DEPLOY]: ✅ APK установлен на устройство")
    except FileNotFoundError:
        print("[APK DEPLOY]: ❌ adb не найден. Установите Android SDK Platform Tools.")
    except subprocess.CalledProcessError as e:
        print(f"[APK DEPLOY]: ❌ Ошибка установки: {e}")


if __name__ == "__main__":
    if "--deploy" in sys.argv:
        deploy()
    else:
        build()
