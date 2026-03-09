import scrapy
from scrapy.linkextractors.lxmlhtml import LxmlLinkExtractor
from sqlalchemy.orm.session import Session

from db.data import get_all_institutes
from scraper.utils import remove_trailing_slash

admission_terms = [
    "admission",
    "announcement",
    "update",
    "notification",
    # "program",
    # "course",
    # "degree",
    "enrollment",
]
word_pattern = r"\b(?:" + "|".join(admission_terms) + r")s?\b"


class UniSpider(scrapy.Spider):
    name = "uni"
    link_extractor = LxmlLinkExtractor(
        canonicalize=True, unique=True, allow=word_pattern
    )
    custom_settings = {
        "FEEDS": {"uni.jsonl": {"format": "jsonlines", "overwrite": True}}
    }

    def __init__(self, *args, **kwargs):
        super(UniSpider, self).__init__(*args, **kwargs)
        self.visited_urls = set()
        self.db: Session = kwargs.pop("db", None)

    def _get_sites(self) -> list[str]:
        all_institutes = get_all_institutes(self.db)
        if all_institutes is not None:
            return [str(institute.website) for institute in all_institutes]
        return []

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

            matched_links.append(clean_link_url)
            print(f"Found matches {response.url} - '{link.url}'")

            if current_depth == 0:
                yield scrapy.Request(
                    url=link.url,
                    callback=self.parse,
                    meta={
                        "original_url": original_url,
                        "depth": 1,
                    },
                )

        item = {
            "site": original_url,
            "matched_links": list(matched_links),
        }
        yield item
