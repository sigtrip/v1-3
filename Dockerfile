
# Используем официальный образ Python как базовый
FROM python:3.9-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все остальные файлы приложения
COPY . .

# Открываем порт, на котором будет работать FastAPI
EXPOSE 8080

# Запускаем приложение в режиме WEB при запуске контейнера
CMD ["python", "main.py", "--web"]
