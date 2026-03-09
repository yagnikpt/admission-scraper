import io
import os
import random
import re

import pandas as pd
import scrapy
from bs4 import BeautifulSoup

from scraper.utils import (
    remove_trailing_slash,
)
from scraper.utils.page import clean_body_content, extract_context
from scraper.utils.pdf import extract_text_from_pdf_bytes


def getUrls() -> list[str]:
    try:
        # Check if file exists first
        if not os.path.exists("uni.jsonl"):
            print("Warning: uni.jsonl file not found")
            return []

        # Open the file and use StringIO to avoid FutureWarning
        with open("uni.jsonl", "r", encoding="utf-8") as f:
            content = f.read()

        # Process only if file has content
        if content.strip():
            df = pd.read_json(io.StringIO(content), lines=True)
            urls = df["matched_links"].tolist()
            urls = [url for sublist in urls for url in sublist]
            urls = list(set(urls))
            random.shuffle(urls)
            return urls
        else:
            print("uni.jsonl file is empty")
            return []
    except Exception as e:
        # More detailed error handling
        print(f"Error reading uni.jsonl: {e}")
        return []


def get_site_from_link(link):
    try:
        # Check if file exists first
        if not os.path.exists("uni.jsonl"):
            print("Warning: uni.jsonl file not found in get_site_from_link")
            return None

        # Open the file and use StringIO to avoid FutureWarning
        with open("uni.jsonl", "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            print("uni.jsonl file is empty in get_site_from_link")
            return None

        data = pd.read_json(io.StringIO(content), lines=True)

        for _, row in data.iterrows():
            if link in row["matched_links"]:
                return row["site"]

        return None
    except Exception as e:
        print(f"Error finding site for link {link}: {e}")
        return None


admission_terms = r"(?:admission|apply|application|deadline|enroll|registration|enrollment|notice|notification|admit)"
date_pattern = (
    r"(?:\b(?:\d{1,2}[-./]\d{1,2}[-./](?:\d{4}|\d{2}))\b|"
    + r"\b(?:\d{1,2}[- ]?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[- ]?\d{2,4})\b|"
    + r"\b(?:\d{4}[-./]\d{1,2}[-./]\d{1,2})\b)"
)
word_pattern = rf"\b{admission_terms}s?\b"


class PagesSpider(scrapy.Spider):
    name = "pages"
    custom_settings = {
        "FEEDS": {"pages.jsonl": {"format": "jsonlines", "overwrite": True}}
    }

    def __init__(self, *args, **kwargs):
        super(PagesSpider, self).__init__(*args, **kwargs)
        self.counter = 0

    def start_requests(self):
        self.urls = getUrls()

        for url in self.urls:
            yield scrapy.Request(
                url=url, callback=self.parse, meta={"original_url": url}
            )

    def parse(self, response):
        if response.url.lower().endswith(
            ".pdf"
        ) or "application/pdf" in response.headers.get("Content-Type", b"").decode(
            "utf-8", "ignore"
        ):
            print(f"\nProcessing PDF: {response.url}\n")
            pdf_text = extract_text_from_pdf_bytes(response.body)
            if not pdf_text:
                return

            date_matches = extract_context(pdf_text, date_pattern)

            if len(date_matches) != 0:
                for date_match in date_matches:
                    if not is_likely_phone_number(date_match["match"]):
                        word_matches = re.findall(
                            word_pattern, date_match["context"], re.IGNORECASE
                        )
                        if word_matches:
                            site = get_site_from_link(response.meta.get("original_url"))
                            yield {
                                "url": remove_trailing_slash(response.url),
                                "site": site,
                                "date": date_match["match"],
                                "context": date_match["context"],
                                "related_dates": date_match.get("related_dates", []),
                                "source_type": "pdf",
                            }

            print(f"processed PDF: {response.url}")
            return

        self.counter += 1
        pdf_link_tags = response.css("a[href$='.pdf']").getall()
        for link_tag in pdf_link_tags:
            soup = BeautifulSoup(link_tag, "html.parser")
            link_href = soup.a.get("href") if soup.a else ""
            text = soup.a.get_text() if soup.a else ""
            if not link_href:
                continue
            text_matches = re.findall(word_pattern, text, re.IGNORECASE)
            url_matches = re.findall(word_pattern, str(link_href), re.IGNORECASE)
            word_matches = [*text_matches, *url_matches]
            if word_matches:
                yield scrapy.Request(
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

        date_matches = extract_context(cleaned_body_content, date_pattern)

        if len(date_matches) != 0:
            for date_match in date_matches:
                if not is_likely_phone_number(date_match["match"]):
                    word_matches = re.findall(
                        word_pattern, date_match["context"], re.IGNORECASE
                    )
                    if word_matches:
                        site = get_site_from_link(response.meta.get("original_url"))
                        yield {
                            "url": remove_trailing_slash(response.url),
                            "site": site,
                            "date": date_match["match"],
                            "context": date_match["context"],
                            "related_dates": date_match.get("related_dates", []),
                            "source_type": "html",
                        }

        print("processed", self.counter, "from", len(self.urls), "urls")


def is_likely_phone_number(text):
    phone_patterns = [
        r"\d+/\d+/\d+/\d+",  # Pattern like 8200/1/2/3
        r"\d+-\d+-\d+",  # Pattern like 91-72-820
        r"\d{4}-\d{2,3}-\d{2,4}",  # Common phone format with hyphens
        r"\d{10,}",  # Any sequence of 10+ digits (most dates won't have this many)
    ]

    # Date-specific validation
    month_names = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    looks_like_date = bool(
        re.search(rf"\b({month_names})\b", text, re.IGNORECASE)
        or re.search(r"\b\d{4}\b", text)
    )  # Has a 4-digit year

    # Check against phone patterns
    for pattern in phone_patterns:
        if re.search(pattern, text):
            return True

    return not looks_like_date
