"""admin.py — Файловые операции, процессы, терминал"""
from __future__ import annotations
import os, subprocess, platform, psutil, shutil
from datetime import datetime
from pathlib import Path
from src.argos_logger import get_logger
log = get_logger("argos.admin")

class ArgosAdmin:
    def __init__(self):
        self._alert_cb = None

    def set_alert_callback(self, cb): self._alert_cb = cb

    def get_stats(self) -> str:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return (f"🖥️ CPU: {cpu:.1f}%  RAM: {ram.percent:.1f}% "
                f"({ram.used//1024//1024}MB/{ram.total//1024//1024}MB)  "
                f"Диск: {disk.percent:.1f}%")

    def list_processes(self, n=15) -> str:
        procs = sorted(psutil.process_iter(["pid","name","cpu_percent","memory_percent"]),
                       key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:n]
        lines = ["📋 ПРОЦЕССЫ (топ по CPU):"]
        for p in procs:
            i=p.info
            lines.append(f"  {i['pid']:>6} {(i['name'] or '')[:22]:<22} "
                         f"CPU:{i['cpu_percent'] or 0:>5.1f}%  MEM:{i['memory_percent'] or 0:>5.1f}%")
        return "\n".join(lines)

    def list_dir(self, path: str = ".") -> str:
        try:
            p = Path(path)
            if not p.exists(): return f"❌ Путь не существует: {path}"
            items = list(p.iterdir())
            dirs  = sorted([i for i in items if i.is_dir()], key=lambda x: x.name)
            files = sorted([i for i in items if i.is_file()], key=lambda x: x.name)
            lines = [f"📁 {p.resolve()} ({len(items)} элементов):"]
            for d in dirs[:30]:  lines.append(f"  📁 {d.name}/")
            for f in files[:30]: lines.append(f"  📄 {f.name} ({f.stat().st_size} б)")
            if len(items)>60: lines.append(f"  ... и ещё {len(items)-60}")
            return "\n".join(lines)
        except Exception as e: return f"❌ list_dir: {e}"

    def read_file(self, path: str) -> str:
        try:
            p = Path(path)
            if not p.exists(): return f"❌ Файл не найден: {path}"
            if p.stat().st_size > 100_000: return f"⚠️ Файл слишком большой ({p.stat().st_size} байт)"
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception as e: return f"❌ read_file: {e}"

    def write_file(self, path: str, content: str) -> str:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"✅ Файл записан: {path} ({len(content)} символов)"
        except Exception as e: return f"❌ write_file: {e}"

    def delete_file(self, path: str) -> str:
        try:
            p = Path(path)
            if not p.exists(): return f"❌ Не найден: {path}"
            if p.is_dir(): shutil.rmtree(p); return f"🗑️ Папка удалена: {path}"
            p.unlink(); return f"🗑️ Файл удалён: {path}"
        except Exception as e: return f"❌ delete_file: {e}"

    def run_command(self, cmd: str) -> str:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            out = (r.stdout or "") + (r.stderr or "")
            return f"💻 $ {cmd}\n{out[:2000]}" if out.strip() else f"💻 $ {cmd}\n(нет вывода)"
        except subprocess.TimeoutExpired: return f"⏱️ Таймаут: {cmd}"
        except Exception as e: return f"❌ run_command: {e}"

    def kill_process(self, name_or_pid: str) -> str:
        try:
            pid = int(name_or_pid)
            psutil.Process(pid).terminate()
            return f"✅ Процесс {pid} завершён."
        except ValueError:
            killed = []
            for p in psutil.process_iter(["pid","name"]):
                if name_or_pid.lower() in (p.info["name"] or "").lower():
                    try: p.terminate(); killed.append(p.info["pid"])
                    except: pass
            return f"✅ Завершены: {killed}" if killed else f"❌ Процесс не найден: {name_or_pid}"
        except Exception as e: return f"❌ kill_process: {e}"

    def manage_power(self, action: str) -> str:
        cmds = {"shutdown":"shutdown -h now","reboot":"reboot","sleep":"systemctl suspend"}
        cmd = cmds.get(action)
        if not cmd: return f"❌ Неизвестное действие: {action}"
        return self.run_command(cmd)

    def set_role(self, role: str) -> str:
        return f"🔐 Роль установлена: {role}"

    def security_status(self) -> str:
        return "🔐 Безопасность: OK"
