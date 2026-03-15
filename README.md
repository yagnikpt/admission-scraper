# Admission Scraper

A Python-based tool for scraping and processing university admission announcements.

## Project Overview

This project automates the collection, processing, and storage of university admission announcements. It uses web scraping (Scrapy) to gather information from university websites, processes the data using LLMs (with a pluggable provider architecture supporting Google Gemini via Vertex AI and Groq), detects content changes and duplicate announcements, and stores structured information in a PostgreSQL database.

## Architecture

The project is organized into several components:

- **Web Scraping (`scraper/`)**: Runs spiders (`UniSpider`, `PagesSpider`) to collect HTML/PDF content and relevant text snippets from university websites. Supports checkpoint-based resume mode for long-running crawls.
- **Orchestration (`main.py`)**: Manages spider execution, reads scraped data, checks for content changes against the database, and triggers LLM processing via CLI flags.
- **LLM Processing (`llm/`)**: Pluggable provider system with an abstract base class (`llm/base.py`) and concrete implementations for Gemini (`llm/providers/gemini.py`) and Groq (`llm/providers/groq.py`). Dynamically selected via the `LLM_PROVIDER` config. Includes duplicate announcement detection using fuzzy string matching (rapidfuzz).
- **Configuration (`config.py`)**: Centralized settings management using Pydantic's `BaseSettings`, loading from `.env` file. Controls LLM provider selection, database URL, and cloud credentials.
- **Database (`db/`)**: Stores processed announcements, programs, institution information, and tracks processed page content using SQLAlchemy ORM.

## Data Processing Pipeline

1.  **Spider Execution**: `main.py` runs `UniSpider` then `PagesSpider`.
2.  **Data Collection**: The spider collects data (context, URL, site) and stores it in `pages.jsonl`.
3.  **Data Loading & Grouping**: `main.py` reads `pages.jsonl` and groups entries by URL.
4.  **Change Detection**: For each URL group, content is merged and compared against the database using SHA-256 hashing via `llm.process.content_changed`.
5.  **Data Extraction**: If content is new or changed, merged content is sent in a single LLM call per URL to extract structured announcement data.
6.  **Duplicate Detection**: Before storing, each extracted announcement title is compared against existing announcements for the same institution using fuzzy matching (rapidfuzz `WRatio`, threshold: 75). Duplicates are skipped.
7.  **Data Storage**: Non-duplicate announcements and related information are stored in the database via functions in `db/data.py`.

## Data Scraping Process

1.  **Spider Execution**: `main.py` initiates the Scrapy process, running `UniSpider` first to identify relevant pages, followed by `PagesSpider` which loads URLs from `uni.jsonl` (output of `UniSpider`) directly in its `__init__` method with validation.
2.  **Content Scraping**: `PagesSpider` scrapes relevant text content (`context`) from target pages and PDFs (including PDF links discovered within pages). It detects PDFs via URL extension, `Content-Type`, and `Content-Disposition` headers.
3.  **Resume Support**: When `--pages-resume` is enabled, Scrapy's `JOBDIR` is set to persist request queues, allowing interrupted crawls to continue from where they left off.
4.  **Processing Orchestration**:
    -   After spiders complete, `main.py` reads `pages.jsonl`.
    -   It compares the scraped URLs and content against the database records.
    -   It skips URLs whose content hasn't changed (hash-based comparison).
5.  **Information Extraction**:
    -   For new or changed pages, `main.py` calls `llm.process.process_page` with the merged content.
    -   A single LLM call is made per URL with all merged text chunks.
    -   The LLM analyzes the content and returns structured data about admission announcements.
6.  **Data Processing & Storage**:
    -   Extracted announcements are checked for duplicates against existing data using fuzzy title matching.
    -   Non-duplicate announcements are stored with associated institution, program, and tag links via `db/data.py`.

## Setup and Usage

### Prerequisites
- Python 3.8+
- PostgreSQL or compatible database
- Google Cloud credentials (for Gemini via Vertex AI) or Groq API key

### Installation
1. Clone the repository
```bash
git clone https://github.com/yagnikpt/admission-scraper.git
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

3. Configure environment variables by copying `.env.example` to `.env` and filling in the values:
```
DATABASE_URL=
GROQ_API_KEY=
GOOGLE_CLOUD_PROJECT=
GOOGLE_CLOUD_LOCATION=
```

4. Seed the initial data (programs, states, tags)

### Running the Scraper

Execute the main script to run the entire pipeline (scraping and processing):
```bash
just start
```
Or directly:
```bash
uv run main.py
```

### CLI Options

| Flag | Description |
|---|---|
| `--cleanup` | Run cleanup to remove old records before processing |
| `--skip-scraping` | Skip spider execution, only process existing `pages.jsonl` |
| `--skip-push` | Skip LLM processing and DB push, only run spiders |
| `--pages-resume` | Enable checkpoint/resume mode for the pages spider |
| `--pages-jobdir DIR` | Set checkpoint directory (default: `.checkpoints/pages`) |
| `--pages-reset-checkpoint` | Reset checkpoint directory before crawling (use with `--pages-resume`) |

## Project Structure
```
admission-scraper/
├── main.py              # CLI entrypoint: orchestrates spiders and processing
├── config.py            # Centralized settings
├── cleanup.py           # Script for cleaning old data from the database
├── base_prompt.txt      # System prompt for LLM extraction
├── scraper/             # Scrapy project
│   ├── spiders/
│   │   ├── uni.py       # Spider to find relevant university pages → uni.jsonl
│   │   └── pages.py     # Spider to extract text context from pages → pages.jsonl
│   ├── pipelines.py     # Scrapy pipelines
│   ├── settings.py      # Scrapy settings
│   └── utils/           # Scraping utilities
├── llm/
│   ├── __init__.py      # LLM provider factory (get_llm based on config)
│   ├── base.py          # Abstract base class for LLM providers
│   ├── schema.py        # Pydantic models for LLM response schema
│   ├── process.py       # Processing logic: change detection, duplicate check, DB storage
│   └── providers/
│       ├── gemini.py    # Google Gemini via Vertex AI provider
│       └── groq.py      # Groq API provider
├── db/
│   ├── models.py        # SQLAlchemy ORM models
│   ├── session.py       # Database session management
│   ├── data.py          # Database CRUD functions
│   └── seed.py          # Script to seed initial data
├── justfile             # Task runner commands
├── pyproject.toml       # Project metadata and dependencies
├── scrapy.cfg           # Scrapy configuration
└── README.md            # This documentation
```

## Further Development

Potential areas for enhancement:
- Adding more LLM providers
- Creating a web interface for viewing and managing scraped data
- Extending to additional educational institutions
