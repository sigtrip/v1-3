
import os
import subprocess

class AcceleratorManager:
    def __init__(self):
        self.gpu_available = self._check_gpu_availability()
        self.tpu_available = self._check_tpu_availability() # Заглушка для TPU
        print(f"DEBUG: AcceleratorManager initialized. GPU: {self.gpu_available}, TPU: {self.tpu_available}")

    def _check_gpu_availability(self):
        # Проверка CUDA (NVIDIA GPUs)
        try:
            import torch
            if torch.cuda.is_available():
                print("DEBUG: PyTorch сообщает, что CUDA GPU доступен.")
                return True
        except ImportError:
            print("DEBUG: PyTorch не установлен, невозможно проверить CUDA GPU.")
        except Exception as e:
            print(f"DEBUG: Ошибка при проверке PyTorch CUDA: {e}")

        # Проверка переменных окружения для GPU
        if os.environ.get("CUDA_VISIBLE_DEVICES", "") != "" or os.environ.get("ROCM_VISIBLE_DEVICES", "") != "":
            print("DEBUG: Обнаружены переменные окружения GPU.")
            return True

        # Проверка NVIDIA GPU через команду nvidia-smi (если установлена)
        try:
            subprocess.check_output(['nvidia-smi'], stderr=subprocess.DEVNULL)
            print("DEBUG: 'nvidia-smi' найден, GPU, вероятно, доступен.")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("DEBUG: 'nvidia-smi' не найден или GPU не обнаружен через 'nvidia-smi'.")
            pass

        return False

    def _check_tpu_availability(self):
        # Заглушка для обнаружения TPU. Реальное обнаружение потребует специфичных библиотек.
        # return 'COLAB_TPU_ADDR' in os.environ # Это специфично для среды Colab.
        return False # Пока упрощено

    def get_accelerator_status(self):
        status = []
        status.append(f"GPU Доступно: {self.gpu_available}")
        status.append(f"TPU Доступно: {self.tpu_available}")
        if self.gpu_available:
            try:
                import torch
                if torch.cuda.is_available():
                    status.append(f"  PyTorch CUDA Устройств: {torch.cuda.device_count()}")
                    for i in range(torch.cuda.device_count()):
                        status.append(f"  - Устройство {i}: {torch.cuda.get_device_name(i)}")
            except ImportError:
                pass # Уже обработано выше
        return "\n".join(status)

    def assign_task_to_accelerator(self, task_description, preferred_accelerator=None):
        # Это будет более сложная логика маршрутизации задач в зависимости от типа и доступности ускорителя
        if preferred_accelerator == "gpu" and self.gpu_available:
            return f"Задача '{task_description}' назначена на GPU."
        elif preferred_accelerator == "tpu" and self.tpu_available:
            return f"Задача '{task_description}' назначена на TPU."
        else:
            return f"Задача '{task_description}' назначена на CPU (предпочтительный ускоритель недоступен)."
