"""Database models for the application."""

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class State(Base):
    """Database model for states."""

    __tablename__ = "states"

    state_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    abbreviation = Column(String(2), nullable=False, unique=True)

    institutions = relationship("Institution", back_populates="state")
    announcements = relationship("Announcement", back_populates="state")


class Institution(Base):
    """Database model for institutions."""

    __tablename__ = "institutions"

    institution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    website = Column(String, nullable=False, unique=True)
    state_id = Column(UUID(as_uuid=True), ForeignKey("states.state_id"), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    state = relationship("State", back_populates="institutions")
    announcements = relationship("Announcement", back_populates="institution")


class Program(Base):
    """Database model for programs."""

    __tablename__ = "programs"

    program_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    degree_level = Column(String, nullable=True)
    duration_months = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    announcements = relationship(
        "Announcement", secondary="program_announcements", back_populates="programs"
    )


class Tag(Base):
    """Database model for tags."""

    __tablename__ = "tags"

    tag_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)

    announcements = relationship(
        "Announcement", secondary="announcement_tags", back_populates="tags"
    )


class Announcement(Base):
    """Database model for announcements."""

    __tablename__ = "announcements"

    announcement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    url = Column(String, nullable=False)
    institution_id = Column(
        UUID(as_uuid=True), ForeignKey("institutions.institution_id"), nullable=True
    )
    state_id = Column(UUID(as_uuid=True), ForeignKey("states.state_id"), nullable=True)
    published_date = Column(Date, nullable=True)
    application_open_date = Column(Date, nullable=True)
    application_deadline = Column(Date, nullable=True)
    term = Column(String, nullable=True)
    contact_info = Column(Text, nullable=True)
    announcement_type = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)
    scraped_page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scraped_pages.scraped_page_id", ondelete="CASCADE"),
        nullable=True,
    )

    programs = relationship(
        "Program", secondary="program_announcements", back_populates="announcements"
    )
    institution = relationship("Institution", back_populates="announcements")
    state = relationship("State", back_populates="announcements")
    tags = relationship(
        "Tag", secondary="announcement_tags", back_populates="announcements"
    )
    scraped_page = relationship("ScrapedPage", back_populates="announcements")


class AnnouncementProgram(Base):
    """Database model for the program_announcements junction table."""

    __tablename__ = "program_announcements"

    program_id = Column(
        UUID(as_uuid=True), ForeignKey("programs.program_id"), primary_key=True
    )
    announcement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("announcements.announcement_id"),
        primary_key=True,
    )


class AnnouncementTags(Base):
    """Database model for the announcement_tags junction table."""

    __tablename__ = "announcement_tags"

    announcement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("announcements.announcement_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tags.tag_id", ondelete="CASCADE"),
        primary_key=True,
    )


class ScrapedPage(Base):
    """Database model for scraped pages tracking."""

    __tablename__ = "scraped_pages"

    scraped_page_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String(255), nullable=False)
    site = Column(String(255), nullable=True)
    last_scraped = Column(DateTime, nullable=False)
    content_hash = Column(String(64), nullable=False)

    announcements = relationship("Announcement", back_populates="scraped_page")
