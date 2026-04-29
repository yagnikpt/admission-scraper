import io
import os
import random
import re

import pandas as pd
import scrapy
from bs4 import BeautifulSoup
from scrapy.http import TextResponse

from scraper.utils import (
    remove_trailing_slash,
)
from scraper.utils.page import clean_body_content, extract_context
from scraper.utils.pdf import extract_text_from_pdf_bytes

admission_terms = r"(?:admission|apply|application|deadline|enroll|registration|enrollment|notice|notification|admit)"
date_pattern = (
    r"(?:\b(?:\d{1,2}[-./]\d{1,2}[-./](?:\d{4}|\d{2}))\b|"
    + r"\b(?:\d{1,2}[- ]?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[- ]?\d{2,4})\b|"
    + r"\b(?:\d{4}[-./]\d{1,2}[-./]\d{1,2})\b)"
)
word_pattern = rf"\b{admission_terms}s?\b"

# Extraction mode: "full_page" sends entire cleaned page text to LLM.
# "context_window" uses the legacy fragment-based approach with a wider window.
EXTRACTION_MODE = "full_page"
# Context window size (tokens before/after) when using "context_window" mode
CONTEXT_WINDOW_SIZE = 250


class PagesSpider(scrapy.Spider):
    name = "pages"
    # Output is handled by SpiderSpecificOutputPipeline.
    # custom_settings = {
    #     "FEEDS": {"pages.jsonl": {"format": "jsonlines", "overwrite": True}}
    # }

    def __init__(self, *args, **kwargs):
        self.resume_mode = kwargs.pop("resume_mode", False)
        super(PagesSpider, self).__init__(*args, **kwargs)
        self.counter = 0
        if not os.path.exists("uni.jsonl"):
            raise FileNotFoundError("uni.jsonl file not found")

        with open("uni.jsonl", "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            raise ValueError("uni.jsonl file is empty")

        data = pd.read_json(io.StringIO(content), lines=True)
        self.uni_rows = data.to_dict(orient="records")

    def _get_urls(self):
        urls = []
        for uni in self.uni_rows:
            urls.extend(uni["matched_links"])

        urls = list(dict.fromkeys(urls))
        if not self.resume_mode:
            random.shuffle(urls)
        return urls

    def _get_site_from_link(self, original_url) -> str | None:
        for uni in self.uni_rows:
            if original_url in uni["matched_links"]:
                return uni["site"]
        return None

    def start_requests(self):
        self.urls = self._get_urls()
        # self.urls = []

        for url in self.urls:
            yield scrapy.Request(
                url=url, callback=self.parse, meta={"original_url": url}
            )

    def parse(self, response):
        content_type = response.headers.get("Content-Type", b"").decode(
            "utf-8", "ignore"
        )
        content_disposition = response.headers.get("Content-Disposition", b"").decode(
            "utf-8", "ignore"
        )

        if (
            response.url.lower().endswith(".pdf")
            or "application/pdf" in content_type
            or ".pdf" in content_disposition.lower()
        ):
            print(f"\nProcessing PDF: {response.url}\n")
            pdf_text = extract_text_from_pdf_bytes(response.body)
            if not pdf_text:
                return

            site = self._get_site_from_link(response.meta.get("original_url"))

            if EXTRACTION_MODE == "full_page":
                # Full page mode: yield entire PDF text if it contains admission keywords
                if re.search(word_pattern, pdf_text, re.IGNORECASE):
                    yield {
                        "url": remove_trailing_slash(response.url),
                        "site": site,
                        "context": pdf_text,
                        "source_type": "pdf",
                    }
            else:
                # Context window mode: extract date-anchored fragments
                yield from self._extract_context_window_items(
                    pdf_text, response.url, site, "pdf"
                )

            print(f"processed PDF: {response.url}")
            return

        self.counter += 1

        if not isinstance(response, TextResponse):
            return

        # Follow ALL PDFs on admission-relevant pages.
        # These pages were already filtered by UniSpider's URL matching,
        # so PDFs here are likely admission-relevant regardless of anchor text.
        pdf_link_tags = response.css("a[href$='.pdf']").getall()
        for link_tag in pdf_link_tags:
            soup = BeautifulSoup(link_tag, "html.parser")
            link_href = soup.a.get("href") if soup.a else ""
            if not link_href:
                continue
            yield response.follow(
                url=str(link_href),
                callback=self.parse,
                meta={
                    "original_url": response.meta.get("original_url"),
                    "is_pdf": True,
                },
            )

        body_content = response.css("body").get()
        if not body_content:
            return

        cleaned_body_content = clean_body_content(body_content)

        site = self._get_site_from_link(response.meta.get("original_url"))

        if EXTRACTION_MODE == "full_page":
            # Full page mode: yield entire cleaned page text if it contains admission keywords
            if re.search(word_pattern, cleaned_body_content, re.IGNORECASE):
                yield {
                    "url": remove_trailing_slash(response.url),
                    "site": site,
                    "context": cleaned_body_content,
                    "source_type": "html",
                }
        else:
            # Context window mode: extract date-anchored fragments with wider window
            yield from self._extract_context_window_items(
                cleaned_body_content, response.url, site, "html"
            )

        print("processed", self.counter, "from", len(self.urls), "urls")

    def _extract_context_window_items(self, text, url, site, source_type):
        """Extract date-anchored context windows with admission keyword matching.

        This is the legacy fragment-based approach, kept for interchangeability.
        Uses a wider context window (CONTEXT_WINDOW_SIZE tokens) than the original
        50-token window to capture more surrounding context.
        """
        date_matches = extract_context(
            text, date_pattern, before=CONTEXT_WINDOW_SIZE, after=CONTEXT_WINDOW_SIZE
        )

        if len(date_matches) != 0:
            for date_match in date_matches:
                if not is_likely_phone_number(date_match["match"]):
                    word_matches = re.findall(
                        word_pattern, date_match["context"], re.IGNORECASE
                    )
                    if word_matches:
                        yield {
                            "url": remove_trailing_slash(url),
                            "site": site,
                            "date": date_match["match"],
                            "context": date_match["context"],
                            "related_dates": date_match.get("related_dates", []),
                            "source_type": source_type,
                        }


def is_likely_phone_number(text):
    """Check if a date-like string is actually a phone number.

    Checks date indicators first (short-circuit) before testing phone patterns.
    This avoids false positives where ISO dates like '2026-01-15' were
    incorrectly classified as phone numbers.
    """
    # If it contains a month name, it's clearly a date
    month_names = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    if re.search(rf"\b({month_names})\b", text, re.IGNORECASE):
        return False

    # ISO date format: YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text.strip()):
        return False

    # Contains a plausible 4-digit year (19xx or 20xx) → likely a date
    if re.search(r"\b(19|20)\d{2}\b", text):
        return False

    phone_patterns = [
        r"\d+/\d+/\d+/\d+",  # Pattern like 8200/1/2/3
        r"\d{10,}",  # Any sequence of 10+ consecutive digits
        r"(?<!\d)\d{3,5}-\d{3,5}-\d{3,5}(?!\d)",  # Phone-like hyphenated segments
    ]

    for pattern in phone_patterns:
        if re.search(pattern, text):
            return True

    return False
