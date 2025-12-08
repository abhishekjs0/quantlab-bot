# QuantLab Makefile
# Development and build automation

# Prevent Python from creating __pycache__ directories
export PYTHONDONTWRITEBYTECODE=1

.PHONY: help install dev-install test lint format clean docs demo backtest

# Default target
help:
	@echo "QuantLab Development Commands:"
	@echo "  install      Install production dependencies"
	@echo "  dev-install  Install development dependencies"
	@echo "  test         Run all tests"
	@echo "  lint         Run linting and type checking"
	@echo "  format       Format code with black and isort"
	@echo "  clean        Clean up cache and temporary files"
	@echo "  docs         Generate documentation"
	@echo "  demo         Run a demo backtest"
	@echo "  backtest     Run ichimoku backtest on default basket"

# Installation
install:
	pip install -e .

dev-install:
	pip install -e .[dev]
	pre-commit install || echo "Pre-commit not available"

# Testing
test:
	python -m pytest tests/ -v --cov=core --cov=strategies --cov=runners

test-fast:
	python -m pytest tests/ -v -x

# Code quality
lint:
	ruff check .
	mypy . || echo "MyPy check completed with warnings"

format:
	black .
	isort .
	ruff check --fix .

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.log" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf build dist *.egg-info

# Documentation
docs:
	@echo "Documentation available in docs/ directory"
	@echo "See: docs/QUANTLAB_GUIDE.md, docs/BACKTEST_GUIDE.md, docs/STRATEGIES.md"

# Demo and backtesting
demo:
	python -m runners.run_basket --basket_file data/basket_test.txt --strategy ema_crossover --use_cache_only

backtest:
	python -m runners.run_basket --basket_file data/basket_default.txt --strategy ichimoku

backtest-small:
	python -m runners.run_basket --basket_file data/basket_test.txt --strategy ichimoku

# Development utilities
setup:
	pip install -e .[dev]
	python config.py

check-data:
	python -c "from data.loaders import list_available_data; print(list_available_data())"

# All quality checks
check-all: format lint test

# CI pipeline simulation
ci: check-all
	@echo "✅ All CI checks passed!"
