import json
import os
import platform
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import psutil

AUDIT_LOG_PATH = "logs/security_audit.log"

ROLE_ALLOWED_BINARIES = {
    "viewer": {"ls", "pwd", "whoami", "date", "uptime", "df", "free", "ps", "head", "tail", "cat", "echo"},
    "operator": {
        "ls",
        "pwd",
        "whoami",
        "date",
        "uptime",
        "df",
        "free",
        "ps",
        "head",
        "tail",
        "cat",
        "echo",
        "ip",
        "ss",
        "netstat",
        "lsof",
        "ping",
        "find",
        "grep",
        "du",
        "top",
    },
    "admin": {
        "ls",
        "pwd",
        "whoami",
        "date",
        "uptime",
        "df",
        "free",
        "ps",
        "head",
        "tail",
        "cat",
        "echo",
        "ip",
        "ss",
        "netstat",
        "lsof",
        "ping",
        "find",
        "grep",
        "du",
        "top",
        "git",
        "python",
        "python3",
        "pip",
        "pip3",
        "systemctl",
        "journalctl",
    },
    "root": {"*"},
}

DANGEROUS_TOKENS = [
    "rm -rf /",
    "mkfs",
    "dd if=",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    ":(){:|:&};:",
    "chmod 777 /",
    "chown -r /",
    "del /f /s /q c:\\",
]

SHELL_META_TOKENS = ["&&", "||", ";", "|", "`", "$(", ">", "<"]


class ArgosAdmin:
    def __init__(self):
        self.os_type = platform.system()
        self.current_role = os.getenv("ARGOS_ROLE", "admin").strip().lower() or "admin"
        if self.current_role not in ROLE_ALLOWED_BINARIES:
            self.current_role = "admin"
        self._alert_cb = None
        os.makedirs("logs", exist_ok=True)

    def set_alert_callback(self, callback):
        self._alert_cb = callback

    def set_role(self, role: str) -> str:
        role_name = (role or "").strip().lower()
        if role_name not in ROLE_ALLOWED_BINARIES:
            return "❌ Неизвестная роль. Доступные: viewer, operator, admin, root"
        self.current_role = role_name
        self._audit(event="role_change", command=f"set_role:{role_name}", allowed=True)
        return f"✅ Роль доступа установлена: {role_name}"

    def security_status(self) -> str:
        allowed = ROLE_ALLOWED_BINARIES.get(self.current_role, set())
        allowed_preview = "*" if "*" in allowed else ", ".join(sorted(list(allowed))[:12])
        return (
            "🛡️ SECURITY STATUS\n"
            f"  Роль: {self.current_role}\n"
            f"  Allowlist: {allowed_preview}\n"
            f"  Audit log: {AUDIT_LOG_PATH}"
        )

    def _audit(self, event: str, command: str, allowed: bool, reason: str = "", user: str = "local"):
        payload = {
            "ts": time.time(),
            "event": event,
            "role": self.current_role,
            "user": user,
            "command": command,
            "allowed": allowed,
            "reason": reason,
        }
        try:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _raise_security_alert(self, message: str):
        if self._alert_cb:
            try:
                self._alert_cb(message)
            except Exception:
                pass

    def _validate_command(self, command: str) -> tuple[bool, str, list[str]]:
        cmd = (command or "").strip()
        if not cmd:
            return False, "Пустая команда", []

        low = cmd.lower()
        for token in DANGEROUS_TOKENS:
            if token in low:
                return False, f"Опасный паттерн: {token}", []

        for token in SHELL_META_TOKENS:
            if token in cmd:
                return False, f"Shell-метасимвол запрещён: {token}", []

        try:
            parts = shlex.split(cmd)
        except Exception:
            return False, "Невалидная shell-синтаксическая команда", []

        if not parts:
            return False, "Пустая команда", []

        binary = Path(parts[0]).name
        allowed_set = ROLE_ALLOWED_BINARIES.get(self.current_role, ROLE_ALLOWED_BINARIES["viewer"])
        if "*" not in allowed_set and binary not in allowed_set:
            return False, f"Команда '{binary}' не разрешена для роли {self.current_role}", []

        return True, "ok", parts

    # ── 1. МОНИТОРИНГ ─────────────────────────────────────
    def get_stats(self):
        c = psutil.cpu_percent(interval=0.5)
        r = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/")
        return f"ЦП: {c}% | ОЗУ: {r}% | " f"Диск: {disk.free // (2**30)}GB свободно | ОС: {self.os_type}"

    def manage_power(self, action):
        if action == "shutdown":
            cmd = "shutdown /s /t 5" if self.os_type == "Windows" else "sudo shutdown now"
            os.system(cmd)
            return "Инициировано отключение энергии."
        return "Неизвестная директива питания."

    # ── 2. ПРОЦЕССЫ ───────────────────────────────────────
    def kill_process(self, process_name):
        killed = False
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] and process_name.lower() in proc.info["name"].lower():
                try:
                    psutil.Process(proc.info["pid"]).terminate()
                    killed = True
                except psutil.AccessDenied:
                    return f"Отказано в доступе. Процесс {process_name} защищён."
        return f"Процесс {process_name} уничтожен." if killed else f"Процесс {process_name} не найден."

    def list_processes(self):
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                procs.append(f"  {p.info['pid']:>6} | {p.info['name'][:30]:<30} | CPU: {p.info['cpu_percent']}%")
            except Exception:
                pass
        header = "PID    | Имя                           | Нагрузка\n" + "-" * 55
        return header + "\n" + "\n".join(procs[:20]) + ("\n..." if len(procs) > 20 else "")

    # ── 3. ФАЙЛОВАЯ СИСТЕМА ───────────────────────────────
    def list_dir(self, path="."):
        try:
            items = os.listdir(path)
            result = []
            for item in items[:20]:
                full = os.path.join(path, item)
                tag = "📁" if os.path.isdir(full) else "📄"
                result.append(f"  {tag} {item}")
            suffix = "\n  ..." if len(items) > 20 else ""
            return f"📂 Содержимое '{path}' ({len(items)} объектов):\n" + "\n".join(result) + suffix
        except Exception as e:
            return f"Ошибка чтения директории: {e}"

    def read_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read(2000)
            suffix = "..." if len(content) == 2000 else ""
            return f"📄 Файл '{path}':\n{content}{suffix}"
        except Exception as e:
            return f"Ошибка чтения файла: {e}"

    def create_file(self, path: str, content: str = "") -> str:
        """Создаёт файл с заданным содержимым."""
        try:
            folder = os.path.dirname(path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            size = os.path.getsize(path)
            return f"✅ Файл создан: {path} ({size} байт)"
        except Exception as e:
            return f"Ошибка создания файла: {e}"

    def append_file(self, path: str, content: str) -> str:
        """Дописывает текст в конец файла."""
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content + "\n")
            return f"✅ Данные добавлены в {path}"
        except Exception as e:
            return f"Ошибка записи в файл: {e}"

    def delete_item(self, path):
        try:
            if os.path.isfile(path):
                os.remove(path)
                return f"🗑️ Файл {path} удалён."
            elif os.path.isdir(path):
                shutil.rmtree(path)
                return f"🗑️ Директория {path} уничтожена."
            else:
                return f"Объект {path} не найден."
        except Exception as e:
            return f"Ошибка удаления: {e}"

    # ── 4. ТЕРМИНАЛ ───────────────────────────────────────
    def run_cmd(self, command, user: str = "local"):
        valid, reason, parts = self._validate_command(command)
        if not valid:
            self._audit(event="cmd_denied", command=command, allowed=False, reason=reason, user=user)
            self._raise_security_alert(f"SECURITY: отклонена команда '{command}'. Причина: {reason}")
            return f"⛔ Команда заблокирована: {reason}"

        self._audit(event="cmd_exec", command=command, allowed=True, user=user)
        try:
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
            if result.returncode != 0:
                return f"❌ Ошибка команды (code={result.returncode}):\n{output[:400]}"
            out = output[:800]
            return f"💻 Вывод:\n{out}" + ("..." if len(output) > 800 else "")
        except subprocess.TimeoutExpired:
            self._audit(event="cmd_timeout", command=command, allowed=True, reason="timeout", user=user)
            return "⏱️ Команда превысила таймаут (30с)."


# README alias
AdminPanel = ArgosAdmin
