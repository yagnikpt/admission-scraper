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
