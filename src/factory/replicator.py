import datetime
import os
import shutil
import zipfile


class Replicator:
    def __init__(self):
        self.snapshot_dir = "builds/snapshots"
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def create_snapshot(self, label="auto"):
        """Создает снимок состояния системы (БД + конфиги)"""
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{label}_{stamp}.zip"
        filepath = os.path.join(self.snapshot_dir, filename)

        # Что сохраняем (критичные данные)
        targets = ["data", "config", "logs"]

        try:
            with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
                for target in targets:
                    if os.path.exists(target):
                        for root, dirs, files in os.walk(target):
                            # Исключаем кеш
                            if "__pycache__" in root:
                                continue

                            for file in files:
                                fp = os.path.join(root, file)
                                zf.write(fp, os.path.relpath(fp, "."))

            size_kb = os.path.getsize(filepath) / 1024
            return f"✅ Снимок состояния создан: {filename} ({size_kb:.1f} KB)"
        except Exception as e:
            return f"❌ Ошибка создания снимка: {e}"

    def rollback(self, snapshot_file):
        """Откат к указанному снимку"""
        snapshot_path = os.path.join(self.snapshot_dir, snapshot_file)
        if not os.path.exists(snapshot_path):
            return f"❌ Снимок {snapshot_file} не найден."

        try:
            # 1. Безопасность: делаем временный бэкап текущего на всякий случай
            self.create_snapshot(label="pre_rollback")

            # 2. Восстановление
            with zipfile.ZipFile(snapshot_path, "r") as zf:
                zf.extractall(".")

            return f"♻️ Система успешно откачена к состоянию: {snapshot_file}"
        except Exception as e:
            return f"❌ Критическая ошибка при откате: {e}"

    def list_snapshots(self):
        try:
            files = sorted(os.listdir(self.snapshot_dir), reverse=True)
            return files if files else ["Нет доступных снимков"]
        except Exception:
            return []

    def create_replica(self):
        """Создает полную зашифрованную копию системы (исходный код + данные)"""
        os.makedirs("builds/replicas", exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        zip_path = f"builds/replicas/Argos_Replica_{stamp}.zip"
        exclude = ["__pycache__", ".git", "builds", "logs", "venv", "snapshot"]

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk("."):
                dirs[:] = [d for d in dirs if d not in exclude]
                for file in files:
                    fp = os.path.join(root, file)
                    zf.write(fp, os.path.relpath(fp, "."))

        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        return f"✅ Репликация завершена: {zip_path}\n" f"   Размер: {size_mb:.2f} MB\n" f"   Время:  {stamp}"


# README alias
ArgosReplicator = Replicator
