import hashlib
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from rapidfuzz import fuzz
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from db.data import (
    get_all_programs,
    get_all_scraped_pages,
    get_all_tags,
    get_institute_from_website,
)
from db.models import Announcement, AnnouncementProgram, AnnouncementTags, ScrapedPage
from db.session import get_db
from llm import get_llm

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 75

# Don't create a global db session - we'll create sessions as needed
# Cached data can be loaded when needed
db_tags = []
db_programs = []
scraped_pages = None
scraped_urls = None


def load_reference_data():
    """Load reference data that needs to be cached"""
    global db_tags, db_programs, scraped_pages, scraped_urls

    # Get a fresh database session
    db = next(get_db())
    try:
        db_tags = get_all_tags(db) or []
        db_programs = get_all_programs(db) or []
        scraped_pages = get_all_scraped_pages(db)
        scraped_urls = (
            [page.url for page in scraped_pages] if scraped_pages is not None else []
        )
    except Exception as e:
        logger.error(f"Error loading reference data: {e}")
    finally:
        db.close()

    return db_tags, db_programs, scraped_pages, scraped_urls


# Initialize reference data
load_reference_data()


def content_changed(db: Session, url, content):
    try:
        record = db.query(ScrapedPage).filter(ScrapedPage.url == url).first()
        if not record:
            return True
        new_hash = hashlib.sha256(content.encode()).hexdigest()
        return new_hash != record.content_hash
    except Exception as e:
        logger.error(f"Error checking content changed: {e}")
        return True


def is_duplicate_announcement(db: Session, institution_id, new_title: str) -> bool:
    """Check if a semantically similar announcement already exists for this institution.

    Uses rapidfuzz WRatio (weighted ratio) to compare the new title against existing
    announcements for the same institution. WRatio handles length differences and
    token reordering well. Returns True if any existing announcement title has a
    similarity score >= SIMILARITY_THRESHOLD.
    """
    existing_announcements = (
        db.query(Announcement.title)
        .filter(Announcement.institution_id == institution_id)
        .all()
    )

    for (existing_title,) in existing_announcements:
        score = fuzz.WRatio(new_title.lower(), existing_title.lower())
        if score >= SIMILARITY_THRESHOLD:
            logger.info(
                f"Duplicate detected (score={score:.1f}): '{new_title}' ~ '{existing_title}'"
            )
            return True

    return False


def process_page(db: Session, url: str, site: str, merged_content: str):
    """Process a page by sending merged content to the LLM and storing results.

    Args:
        db: Database session
        url: The page URL
        site: The institution website URL
        merged_content: All text chunks for this URL merged into a single string
    """
    try:
        # Get reference data if not already loaded
        global db_tags, db_programs
        if db_tags is None or db_programs is None:
            raise Exception("Reference data not loaded")

        scraped_info = db.query(ScrapedPage).filter(ScrapedPage.url == url).first()

        if scraped_info:
            related_announcements = scraped_info.announcements
            if related_announcements:
                for announcement in related_announcements:
                    db.delete(announcement)

        # Single LLM call with all merged content for this URL
        extract_and_store_data(db, url, site, merged_content)

        # Update scraped page record
        try:
            content_hash = hashlib.sha256(merged_content.encode()).hexdigest()

            if scraped_info is not None:
                db.execute(
                    update(ScrapedPage)
                    .where(ScrapedPage.url == url)
                    .values(
                        last_scraped=datetime.now(ZoneInfo("Asia/Kolkata")),
                        content_hash=content_hash,
                    )
                )
            else:
                scraped_info = ScrapedPage(
                    url=url,
                    site=site,
                    last_scraped=datetime.now(ZoneInfo("Asia/Kolkata")),
                    content_hash=content_hash,
                )
                db.add(scraped_info)
                db.flush()

            if scraped_info:
                anns = db.query(Announcement).filter(Announcement.url == url).all()
                for ann in anns:
                    ann.scraped_page_id = scraped_info.scraped_page_id

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating scraped page info for {url}: {e}")

    except OperationalError as e:
        logger.error(f"Database connection error in process_page: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in process_page for {url}: {e}")
        if db:
            db.rollback()
    finally:
        if db:
            db.close()


def extract_and_store_data(db: Session, url: str, site: str, content: str):
    """Extract announcements from content via LLM and store non-duplicate ones.

    Args:
        db: Database session
        url: The page URL
        site: The institution website URL
        content: The merged text content to send to the LLM
    """
    llm = get_llm()
    extracted_data = llm.extract_announcements(content, url)
    for announcement in extracted_data.announcements:
        institute = get_institute_from_website(db, site)
        if institute:
            # Check for semantic duplicates before inserting
            if is_duplicate_announcement(
                db, institute.institution_id, announcement.title
            ):
                logger.info(
                    f"Skipping duplicate announcement: '{announcement.title}' for {institute.name}"
                )
                continue

            programs = announcement.programs_courses
            tags = announcement.tags

            announcement_data = {
                key: value
                for key, value in announcement.model_dump().items()
                if key != "programs_courses" and key != "tags"
            }
            ann = Announcement(
                institution_id=institute.institution_id,
                state_id=institute.state_id,
                url=url,
                **announcement_data,
            )
            db.add(ann)
            db.flush()
            announcement_id = ann.announcement_id

            for program in programs:
                program_instance = next(
                    (x for x in db_programs if x.name == program), None
                )
                if program_instance:
                    announcement_program = AnnouncementProgram(
                        announcement_id=announcement_id,
                        program_id=program_instance.program_id,
                    )
                    db.add(announcement_program)

            for tag in tags:
                tag_instance = next((x for x in db_tags if x.name == tag), None)
                if tag_instance:
                    try:
                        announcement_tags = AnnouncementTags(
                            announcement_id=announcement_id,
                            tag_id=tag_instance.tag_id,
                        )
                        db.add(announcement_tags)
                    except IntegrityError:
                        # Log and skip duplicate tags instead of failing
                        db.rollback()
                        logger.warning(
                            f"Duplicate tag {tag} for announcement {announcement_id}"
                        )
            db.commit()
        else:
            logger.warning(f"No matching institute found for URL: {site}")
