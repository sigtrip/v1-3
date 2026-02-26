import os
import zipfile
import datetime

class Replicator:
    def create_replica(self):
        """Создает полную зашифрованную копию системы"""
        os.makedirs("builds/replicas", exist_ok=True)
        stamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        zip_path = f"builds/replicas/Argos_Replica_{stamp}.zip"
        exclude  = ["__pycache__", ".git", "builds", "logs", "venv"]

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk("."):
                dirs[:] = [d for d in dirs if d not in exclude]
                for file in files:
                    fp = os.path.join(root, file)
                    zf.write(fp, os.path.relpath(fp, "."))

        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        return (
            f"✅ Репликация завершена: {zip_path}\n"
            f"   Размер: {size_mb:.2f} MB\n"
            f"   Время:  {stamp}"
        )
