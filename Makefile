# Default target (runs if you just type `make`)
.DEFAULT_GOAL := help

PYTHON := uv run

install:
	uv sync

start:
	$(PYTHON) main.py

cleanup:
	$(PYTHON) cleanup.py

skip_scrape:
	$(PYTHON) main.py --skip-scraping

skip_push:
	$(PYTHON) main.py --skip-push

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache

help:
	@echo "Available targets:"
	@echo "  install   - install project dependencies"
	@echo "  start     - start the main application"
	@echo "  cleanup   - run data cleanup tasks"
	@echo "  skip_scrape - run main application skipping scraping step"
	@echo "  skip_push - run main application skipping data pushing step"
	@echo "  clean     - remove temporary files and caches"
