import psutil
import platform
import os
import shutil
import subprocess

class ArgosAdmin:
    def __init__(self):
        self.os_type = platform.system()

    # ── 1. МОНИТОРИНГ ─────────────────────────────────────
    def get_stats(self):
        c = psutil.cpu_percent(interval=0.5)
        r = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/')
        return (f"ЦП: {c}% | ОЗУ: {r}% | "
                f"Диск: {disk.free // (2**30)}GB свободно | ОС: {self.os_type}")

    def manage_power(self, action):
        if action == "shutdown":
            cmd = "shutdown /s /t 5" if self.os_type == "Windows" else "sudo shutdown now"
            os.system(cmd)
            return "Инициировано отключение энергии."
        return "Неизвестная директива питания."

    # ── 2. ПРОЦЕССЫ ───────────────────────────────────────
    def kill_process(self, process_name):
        killed = False
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                try:
                    psutil.Process(proc.info['pid']).terminate()
                    killed = True
                except psutil.AccessDenied:
                    return f"Отказано в доступе. Процесс {process_name} защищён."
        return f"Процесс {process_name} уничтожен." if killed else f"Процесс {process_name} не найден."

    def list_processes(self):
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
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
                tag  = "📁" if os.path.isdir(full) else "📄"
                result.append(f"  {tag} {item}")
            suffix = "\n  ..." if len(items) > 20 else ""
            return f"📂 Содержимое '{path}' ({len(items)} объектов):\n" + "\n".join(result) + suffix
        except Exception as e:
            return f"Ошибка чтения директории: {e}"

    def read_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
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
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            size = os.path.getsize(path)
            return f"✅ Файл создан: {path} ({size} байт)"
        except Exception as e:
            return f"Ошибка создания файла: {e}"

    def append_file(self, path: str, content: str) -> str:
        """Дописывает текст в конец файла."""
        try:
            with open(path, 'a', encoding='utf-8') as f:
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
    def run_cmd(self, command):
        if any(bad in command.lower() for bad in ["rm -rf /", "format c:", "del /f /s /q c:\\"]):
            return "⛔ Действие заблокировано протоколом самосохранения."
        try:
            result = subprocess.check_output(
                command, shell=True, stderr=subprocess.STDOUT,
                text=True, timeout=30
            )
            out = result[:800]
            return f"💻 Вывод:\n{out}" + ("..." if len(result) > 800 else "")
        except subprocess.CalledProcessError as e:
            return f"❌ Ошибка команды:\n{e.output[:400]}"
        except subprocess.TimeoutExpired:
            return "⏱️ Команда превысила таймаут (30с)."
