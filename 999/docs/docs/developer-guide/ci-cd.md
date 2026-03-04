# CI/CD

## GitHub Actions

Проект использует два workflow:

### CI (`ci.yml`)

Запускается на `push` в main/develop и на `pull_request` в main.

| Job     | Описание                                  |
|---------|-------------------------------------------|
| lint    | Black, isort, flake8, mypy                |
| test    | pytest с coverage, health_check           |
| smoke   | Headless boot (25 сек timeout)            |
| docker  | Сборка Docker-образа (только на main)     |

### Release (`release.yml`)

Автоматический релиз при мёрдже в main:

1. **Semantic Release** анализирует коммиты (conventional commits)
2. Генерирует тэг `vX.Y.Z`
3. Обновляет `CHANGELOG.md`
4. Создаёт GitHub Release

#### Conventional Commits

| Префикс   | Bump    | Пример                                |
|-----------|---------|---------------------------------------|
| `feat:`   | minor   | `feat: WireGuard transport`           |
| `fix:`    | patch   | `fix: circuit breaker cooldown`       |
| `perf:`   | patch   | `perf: optimize consensus scoring`    |
| `refactor:` | patch | `refactor: extract transport base`    |

## Локальный запуск

### Тесты

```bash
# Все тесты
pytest -q

# С coverage
pytest --cov=src --cov-report=term-missing

# Конкретный модуль
pytest tests/test_p2p.py -v
```

### Линтеры

```bash
pip install -r requirements-dev.txt

black src/ tests/
isort src/ tests/
flake8 src/
mypy src/
```

### Health Check

```bash
python health_check.py
# Summary: total=124 ok=124 fail=0
```

## Docker

```bash
docker build -t argos:latest .
docker run -d -p 8080:8080 --name argos argos:latest
```

## Сборка

| Платформа  | Команда                         | Результат                |
|-----------|---------------------------------|--------------------------|
| Windows   | `python build_exe.py`           | `dist/argos.exe`         |
| Windows   | `python setup_builder.py`       | `setup_argos.exe`        |
| Android   | `python build_apk.py`           | `bin/*.apk`              |
| Android   | `python build_apk.py --release` | signed APK               |
| Docker    | `docker build -t argos .`       | Docker image             |
