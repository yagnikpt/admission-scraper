import click
import pandas as pd
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from cleanup import remove_data_older_than
from db.data import get_all_scraped_pages
from db.session import get_db
from llm.process import content_changed, process_page
from scraper.spiders.pages import PagesSpider
from scraper.spiders.uni import UniSpider

settings = get_project_settings()


@click.command()
@click.option("--cleanup", is_flag=True, help="Enable cleanup mode.")
@click.option("--skip-scraping", is_flag=True, help="Skip scraping process.")
@click.option(
    "--skip-push", is_flag=True, help="Skip processing and pushing data to db."
)
def main(cleanup, skip_scraping, skip_push):
    db = next(get_db())

    if cleanup:
        print("Running cleanup...")
        remove_data_older_than(db, 30)
        print("Cleanup completed.")

    if not skip_scraping:
        process = CrawlerProcess(settings)

        deferred = process.crawl(UniSpider, db=db)
        deferred.addCallbacks(
            lambda _: db.close() if skip_push else lambda _: None,
            lambda _: process.crawl(PagesSpider),
        )
        # deferred = process.crawl(PagesSpider)
        process.start()

    if not skip_push:
        try:
            df = pd.read_json("pages.jsonl", lines=True)
            result = [
                {"url": url, "items": group.to_dict(orient="records")}
                for url, group in df.groupby("url")
            ]

            scraped_pages = get_all_scraped_pages(db)
            scraped_urls = (
                [page.url for page in scraped_pages]
                if scraped_pages is not None
                else []
            )

            for i, row in enumerate(result):
                print("\nProcessing group", i + 1, "of", len(result))
                if row["url"] in scraped_urls:
                    print(f"Skipping {row['url']}")
                    continue

                merged_content = " ".join(
                    [
                        item["context"]
                        for item in row["items"]
                        if item["context"] is not None
                    ]
                )
                if not content_changed(db, row["url"], merged_content):
                    print(f"Skipping unchanged content for {row['url']}")
                    continue
                process_page(db, row["url"], row["items"][0]["site"], row["items"])
                print(f"Processed group {i + 1} - {row['url']}")
        except Exception as e:
            print(f"Error processing group: {e}")


if __name__ == "__main__":
    main()
