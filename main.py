import os
import shutil

import click
import pandas as pd
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from cleanup import remove_data_older_than
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
@click.option(
    "--pages-resume",
    is_flag=True,
    help="Enable checkpoint/resume mode for pages spider.",
)
@click.option(
    "--pages-jobdir",
    default=".checkpoints/pages",
    show_default=True,
    help="Checkpoint directory used by Scrapy JOBDIR in pages resume mode.",
)
@click.option(
    "--pages-reset-checkpoint",
    is_flag=True,
    help="Reset pages checkpoint directory before crawling (requires --pages-resume).",
)
def main(
    cleanup,
    skip_scraping,
    skip_push,
    pages_resume,
    pages_jobdir,
    pages_reset_checkpoint,
):
    db = next(get_db())

    if cleanup:
        print("Running cleanup...")
        remove_data_older_than(db, 30)
        print("Cleanup completed.")

    if not skip_scraping:
        process_settings = settings.copy()

        if pages_resume:
            if pages_reset_checkpoint:
                if os.path.isdir(pages_jobdir):
                    shutil.rmtree(pages_jobdir)
                if os.path.exists("pages.jsonl"):
                    os.remove("pages.jsonl")

            process_settings.set("JOBDIR", pages_jobdir, priority="cmdline")

            # Output is handled by SpiderSpecificOutputPipeline.
            # process_settings.set(
            #     "FEEDS",
            #     {"pages.jsonl": {"format": "jsonlines", "overwrite": False}},
            #     priority="cmdline",
            # )

        spider_resume = pages_resume and not pages_reset_checkpoint
        process = CrawlerProcess(process_settings)

        # deferred = process.crawl(UniSpider, db=db)
        # # deferred.addCallbacks(
        # #     lambda _: process.crawl(PagesSpider, resume_mode=spider_resume),
        # # )
        # # deferred.addCallbacks(
        # #     lambda _: db.close() if skip_push else lambda _: None,
        # # )

        process.crawl(PagesSpider, resume_mode=spider_resume)
        process.start()

    if not skip_push:
        try:
            df = pd.read_json("pages.jsonl", lines=True)
            result = [
                {"url": url, "items": group.to_dict(orient="records")}
                for url, group in df.groupby("url")
            ]

            for i, row in enumerate(result):
                print(
                    "\nProcessing group",
                    i + 1,
                    "of",
                    len(result),
                    "with len of items",
                    len(row["items"]),
                )

                merged_content = "\n---\n".join(
                    [
                        item["context"]
                        for item in row["items"]
                        if item["context"] is not None
                    ]
                )
                if not content_changed(db, row["url"], merged_content):
                    print(f"Skipping unchanged content for {row['url']}")
                    continue
                process_page(db, row["url"], row["items"][0]["site"], merged_content)
                print(f"Processed group {i + 1} - {row['url']}")
        except Exception as e:
            print(f"Error processing group: {e}")


if __name__ == "__main__":
    main()
