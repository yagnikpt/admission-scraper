from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from db.models import ScrapedPage, Announcement
from db.session import get_db
from sqlalchemy.orm import Session


def remove_data_older_than(db: Session, days: int):
    cutoff_date = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(days=days)

    old_pages = (
        db.query(ScrapedPage).filter(ScrapedPage.last_scraped < cutoff_date).all()
    )

    print(f"Removing {len(old_pages)} scraped pages older than {days} days.")
    counter = 1
    for page in old_pages:
        print(f"Removing page {counter} of {len(old_pages)}: {page.url}")
        counter += 1
        announcements = page.announcements
        for announcement in announcements:
            db.delete(announcement)
        db.delete(page)

    announcements_without_scraped_page = (
        db.query(Announcement)
        .filter(Announcement.scraped_page_id == None)  # noqa: E711
        .all()
    )
    print(
        f"Removing {len(announcements_without_scraped_page)} announcements without scraped page."
    )
    counter = 1
    for announcement in announcements_without_scraped_page:
        print(
            f"Removing announcement {counter} of {len(announcements_without_scraped_page)}: {announcement.announcement_id}"
        )
        counter += 1
        db.delete(announcement)

    db.commit()


if __name__ == "__main__":
    db = next(get_db())
    remove_data_older_than(db, 30)
