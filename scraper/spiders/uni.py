from urllib.parse import urlparse

import scrapy
from scrapy.linkextractors.lxmlhtml import LxmlLinkExtractor
from sqlalchemy.orm.session import Session

from config import settings
from db.data import get_all_institutes
from scraper.utils import remove_trailing_slash

admission_terms = [
    "admission",
    "announcement",
    "notification",
    "enrollment",
    "prospectus",
    "merit",
    "cutoff",
    "counselling",
    "counseling",
    "seat-matrix",
    "selection",
    "result",
    "apply",
    "application",
    "phd",
    "mtech",
    "mba",
    "pgadm",
    "ugadm",
    "pravesh",
    "avedan",
]
word_pattern = r"\b(?:" + "|".join(admission_terms) + r")s?\b"


class UniSpider(scrapy.Spider):
    name = "uni"
    link_extractor = LxmlLinkExtractor(
        canonicalize=True, unique=True, allow=word_pattern
    )
    # Output is handled by SpiderSpecificOutputPipeline.
    # custom_settings = {
    #     "FEEDS": {"uni.jsonl": {"format": "jsonlines", "overwrite": True}}
    # }

    def __init__(self, *args, **kwargs):
        super(UniSpider, self).__init__(*args, **kwargs)
        self.visited_urls = set()
        self.db: Session = kwargs.pop("db", None)
        self.max_depth = settings.max_crawl_depth

    def _get_sites(self) -> list[str]:
        all_institutes = get_all_institutes(self.db)
        if all_institutes is not None:
            return [str(institute.website) for institute in all_institutes]
        return []

    @staticmethod
    def _get_site_root(url):
        """Extract the root domain URL (scheme + netloc) from a full URL.

        e.g. 'https://acu.edu.in/some/deep/page' -> 'https://acu.edu.in'
        """
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _is_same_domain(self, url, original_url):
        """Check if URL belongs to the same domain as the original."""
        return urlparse(url).netloc == urlparse(original_url).netloc

    def start_requests(self):
        urls = self._get_sites()
        for url in urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={"original_url": url, "depth": 0},
            )

    def parse(self, response):
        original_url = response.meta.get("original_url")
        current_depth = response.meta.get("depth", 0)
        current_url = remove_trailing_slash(response.url)

        if current_url in self.visited_urls:
            return
        self.visited_urls.add(current_url)

        matched_links = []

        for link in self.link_extractor.extract_links(response):
            clean_link_url = remove_trailing_slash(link.url)

            if clean_link_url in self.visited_urls:
                continue

            # Only include same-domain links — skip social share buttons,
            # off-site trackers, etc.
            if not self._is_same_domain(link.url, original_url):
                continue

            matched_links.append(clean_link_url)
            print(f"Found matches {response.url} - '{link.url}'")

            if current_depth < self.max_depth:
                yield scrapy.Request(
                    url=link.url,
                    callback=self.parse,
                    meta={
                        "original_url": original_url,
                        "depth": current_depth + 1,
                    },
                )

        # Always use the root domain as site for consistent aggregation,
        # regardless of what page we're currently on or if the DB stored
        # a deep URL.
        site_root = self._get_site_root(original_url)

        item = {
            "site": site_root,
            "matched_links": list(matched_links),
        }
        yield item
