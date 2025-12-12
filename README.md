# Admission Scraper

A Python-based tool for scraping and processing university admission announcements.

## Project Overview

This project is designed to automate the collection, processing, and storage of university admission announcements. It uses web scraping techniques (Scrapy) to gather information from university websites, processes the data using LLMs (specifically Google's Gemini via helper functions), checks for content changes, and stores structured information in a database.

## Architecture

The project is organized into several components:

- **Web Scraping (Scrapy)**: Runs spiders (`UniSpider`, `PagesSpider`) to collect HTML content and relevant text snippets from university websites.
- **Orchestration (`main.py`)**: Manages the execution of spiders, reads the scraped data, checks for content changes against the database, and triggers LLM processing.
- **LLM Processing (`llm/`)**: Uses Google's Gemini (via `llm/gemini.py` and `llm/process.py`) to extract structured data from the collected text snippets.
- **Database (`db/`)**: Stores processed announcements, programs, institution information, and tracks processed page content.

## Data Processing Pipeline

1.  **Spider Execution**: `main.py` runs `UniSpider` then `PagesSpider`.
2.  **Data Collection**: Spiders store collected data (context, URL, site) in `pages.jsonl`.
3.  **Data Loading & Grouping**: `main.py` reads `pages.jsonl` and groups entries by URL.
4.  **Change Detection**: For each URL, `main.py` checks if the URL exists in the database and if the merged content has changed since the last processing using `llm.process.content_changed`.
5.  **Data Extraction**: If the page is new or content has changed, `main.py` calls `llm.process.process_page`, which uses Gemini to extract structured announcement data.
6.  **Data Storage**: Extracted announcements and related information are stored in the database via functions in `db/data.py`.

## Data Scraping Process

The data scraping and processing follow these steps:

1.  **Spider Execution**: `main.py` initiates the Scrapy process, running `UniSpider` first to identify relevant pages, followed by `PagesSpider`.
2.  **Initial Scraping**: `PagesSpider` scrapes relevant text content (`context`) from target pages identified by `UniSpider` and saves it along with the `url` and `site` to `pages.jsonl`.
3.  **Processing Orchestration**:
    -   After spiders complete, `main.py` reads `pages.jsonl`.
    -   It compares the scraped URLs and content against the database records.
    -   It skips URLs that have already been processed and whose content hasn't changed.
4.  **Information Extraction**:
    -   For new or changed pages, `main.py` calls `llm.process.process_page`.
    -   This function sends the relevant content snippets to Gemini (via `llm.gemini.extract_with_gemini`).
    -   Gemini analyzes the content and returns structured data about admission announcements.
5.  **Data Processing & Storage**:
    -   The `process_page` function takes the structured data from Gemini.
    -   It identifies the associated institution, processes announcement details, links programs, and stores everything in the database using functions from `db/data.py`.

6.  **Database Structure**:
   - `Announcement`: Stores announcement details with links to institutions
   - `AnnouncementProgram`: Maps announcements to relevant academic programs
   - Additional tables for institutions, programs, and states

## Setup and Usage

### Prerequisites
- Python 3.8+
- PostgreSQL or compatible database

### Installation
1. Clone the repository
```bash
git clone https://github.com/yagnik-patel-47/admission-scraper.git
cd admission-scraper
```

2. Install dependencies using uv (recommended)
```bash
uv sync
```
Or using pip:
```bash
pip install -r requirements.txt
```

3. Configure database connection in the appropriate configuration file and seed the initial data

### Running the Scraper

Execute the main script to run the entire pipeline (spiders and processing):
```bash
make start
```
Or directly:
```bash
python main.py
```

Additional commands:
- Skip scraping: `make skip_scrape` or `python main.py --skip-scraping`
- Skip data push: `make skip_push` or `python main.py --skip-push`
- Run cleanup: `make cleanup` or `python cleanup.py`

## Project Structure
```
admission_scraper/
├── main.py             # Main script to orchestrate spiders and processing
├── admission_scraper/  # Scrapy project package dir
│   ├── spiders/
│   │   ├── uni.py      # Spider to find relevant university pages
│   │   └── pages.py    # Spider to extract text context from pages
│   ├── pipelines.py    # Scrapy pipelines
│   └── settings.py     # Scrapy settings
├── db/
│   ├── models.py       # Database ORM models (SQLAlchemy)
│   ├── session.py      # Database session management
│   ├── data.py         # Functions for database interactions (CRUD)
│   └── seed.py         # Script to seed initial data
├── llm/
│   ├── gemini.py       # Google Gemini API interaction logic
│   ├── process.py      # Core logic for processing scraped text with LLM and saving to DB
│   └── utils.py        # Utility functions for LLM processing
├── pages.jsonl         # Default output file for raw scraped data from PagesSpider
├── cleanup.py          # Script for data cleanup
├── requirements.txt    # Project dependencies
├── scrapy.cfg          # Scrapy configuration file
└── README.md           # This documentation
```

## Further Development

Potential areas for enhancement:
- Adding more LLM processors for comparison
- Creating a web interface for viewing and managing scraped data
- Extending to additional educational institutions
