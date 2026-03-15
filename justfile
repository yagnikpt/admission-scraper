# run the scraper -> process -> push to db
start:
    uv run main.py

# install packages
install:
    uv sync

# clean older records in db
clean:
    uv run cleanup.py

# process the scraped content and push to db
process_only:
    uv run main.py --skip-scraping

# run the scraper only
scrape_only:
    uv run main.py --skip-push

# run pages scraper in resume mode only
scrape_resume:
    if [ ! -s pages.jsonl ]; then \
        uv run main.py --skip-push --pages-resume --pages-reset-checkpoint; \
    else \
        uv run main.py --skip-push --pages-resume; \
    fi

# run pages scraper in resume mode and reset checkpoint
scrape_resume_reset:
    uv run main.py --skip-push --pages-resume --pages-reset-checkpoint

# run full pipeline in resume mode
start_resume:
    uv run main.py --pages-resume
