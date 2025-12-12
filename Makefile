# Default target (runs if you just type `make`)
.DEFAULT_GOAL := help

PYTHON := uv run

install:
	uv sync

start:
	$(PYTHON) main.py

cleanup:
	$(PYTHON) cleanup.py

process_only:
	$(PYTHON) main.py --skip-scraping

scrape_only:
	$(PYTHON) main.py --skip-push

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache

help:
	@echo "Available targets:"
	@echo "  install   - install project dependencies"
	@echo "  start     - start the main application"
	@echo "  cleanup   - run data cleanup tasks"
	@echo "  process_only - run main application skipping scraping step"
	@echo "  scrape_only - run main application skipping data pushing step"
	@echo "  clean     - remove temporary files and caches"
