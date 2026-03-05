.PHONY: help install install-dev test lint format clean run docker build-apk

# Default target
help:
	@echo "ARGOS Universal OS - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo "  make setup-env        Setup .env from template"
	@echo "  make setup-secrets    Generate secrets automatically"
	@echo "  make check-ready      Check system readiness"
	@echo ""
	@echo "Development:"
	@echo "  make lint             Run all linters (black, isort, flake8, mypy)"
	@echo "  make format           Auto-format code with black and isort"
	@echo "  make test             Run tests with pytest"
	@echo "  make security         Run security checks (bandit, pip-audit)"
	@echo "  make pre-commit       Install pre-commit hooks"
	@echo ""
	@echo "Running:"
	@echo "  make run              Run desktop GUI"
	@echo "  make run-headless     Run without GUI"
	@echo "  make run-dashboard    Run with web dashboard"
	@echo ""
	@echo "Building:"
	@echo "  make build-apk        Build Android APK"
	@echo "  make build-exe        Build Windows EXE"
	@echo "  make docker           Build Docker image"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Clean build artifacts and cache"
	@echo "  make health           Run health check"

# ─── Setup ───────────────────────────────────────────────────

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install pre-commit bandit pip-audit

setup-env:
	@if [ ! -f .env ]; then \
		python setup_secrets.py --auto; \
		echo "✅ Created .env with auto-generated secrets"; \
		echo "⚠️  Please edit .env and add your API keys"; \
	else \
		echo "⚠️  .env already exists"; \
		echo "Run 'python setup_secrets.py --check' to verify"; \
	fi

setup-secrets:
	python setup_secrets.py

check-ready:
	python check_readiness.py

check-ready-quick:
	python check_readiness.py --quick

# ─── Development ─────────────────────────────────────────────

lint:
	@echo "Running Black..."
	black --check --diff src/ tests/ main.py || true
	@echo ""
	@echo "Running isort..."
	isort --check-only --diff src/ tests/ main.py || true
	@echo ""
	@echo "Running Flake8..."
	flake8 src/ tests/ main.py --max-line-length=120 --extend-ignore=E203,W503 || true
	@echo ""
	@echo "Running Mypy..."
	mypy src/ --ignore-missing-imports || true

format:
	@echo "Formatting with Black..."
	black src/ tests/ main.py
	@echo "Sorting imports with isort..."
	isort src/ tests/ main.py
	@echo "✅ Code formatted"

test:
	pytest -v --cov=src --cov-report=term-missing --cov-report=html

security:
	@echo "Running Bandit security scan..."
	bandit -r src/ -c pyproject.toml || true
	@echo ""
	@echo "Running pip-audit..."
	pip-audit --desc || true

pre-commit:
	pre-commit install
	@echo "✅ Pre-commit hooks installed"

# ─── Running ─────────────────────────────────────────────────

run:
	python main.py

run-headless:
	python main.py --no-gui

run-dashboard:
	python main.py --dashboard

health:
	python health_check.py

# ─── Building ────────────────────────────────────────────────

build-apk:
	@echo "Building Android APK..."
	buildozer android debug
	@echo "✅ APK built: bin/*.apk"

build-exe:
	@echo "Building Windows EXE..."
	python build_exe.py
	@echo "✅ EXE built: dist/argos.exe"

docker:
	@echo "Building Docker image..."
	docker build -t argos:latest .
	@echo "✅ Docker image built: argos:latest"

docker-run:
	docker run -d \
		--name argos \
		--env-file .env \
		-p 8080:8080 \
		-p 55771:55771 \
		-v $(PWD)/logs:/app/logs \
		-v $(PWD)/config:/app/config \
		argos:latest

# ─── Maintenance ─────────────────────────────────────────────

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "✅ Cleaned"

clean-all: clean
	@echo "Cleaning buildozer cache..."
	rm -rf .buildozer
	@echo "✅ Deep cleaned"
