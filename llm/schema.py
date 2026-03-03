import enum
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, create_model


class AnnouncementType(str, enum.Enum):
    admission_dates = "admission_dates"
    contact_info = "contact_info"
    exam_info = "exam_info"
    result_info = "result_info"
    general = "general"


def make_announcement_model(programs: list, tags: list):
    ProgramEnum = enum.Enum(
        "ProgramEnum",
        {p.name: p.name for p in programs},
        type=str,
    )
    TagEnum = enum.Enum(
        "TagEnum",
        {t.name: t.name for t in tags},
        type=str,
    )

    class Announcement(BaseModel):
        model_config = ConfigDict(extra="forbid", use_enum_values=True)
        title: str
        content: str
        announcement_type: AnnouncementType
        published_date: Optional[str] = Field(
            default=None,
            pattern=r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?([Zz]|[+-]\d{2}:\d{2})?)?$",
        )
        application_open_date: Optional[str] = Field(
            default=None,
            pattern=r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?([Zz]|[+-]\d{2}:\d{2})?)?$",
        )
        application_deadline: Optional[str] = Field(
            default=None,
            pattern=r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?([Zz]|[+-]\d{2}:\d{2})?)?$",
        )
        term: Optional[str] = None
        contact_info: Optional[str] = None

    AnnouncementFull = create_model(
        "AnnouncementFull",
        __base__=Announcement,
        programs_courses=(list[ProgramEnum], Field(default_factory=list)),
        tags=(list[TagEnum], Field(default_factory=list)),
    )

    AnnouncementList = list[AnnouncementFull]
    AnnouncementResponse = create_model(
        "AnnouncementResponse",
        __config__=ConfigDict(extra="forbid"),
        announcements=(AnnouncementList, ...),
    )

    return AnnouncementResponse
