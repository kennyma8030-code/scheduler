"""Postgres schema for the static half of the SOC data.

Deliberately excluded: whether a section is open. That flips every 30 seconds
(see API_NOTES.md), and re-writing 12k rows on that cadence to persist a boolean
we can refetch in 27 KB would be pure waste. Open/closed is overlaid at read
time from ``SOCClient.open_section_indexes``.

Everything here is stable for the whole semester, so it is synced once per term.

Connection comes from ``DATABASE_URL``; without it we fall back to a local
SQLite file so the same models work in development. The schema uses no
Postgres-only column types for that reason.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

DEFAULT_URL = "sqlite:///app.db"

# The sync CLI runs outside FastAPI, which is where main.py normally does this.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    # Heroku-style URLs use the deprecated postgres:// scheme SQLAlchemy dropped.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Base(DeclarativeBase):
    pass


class Term(Base):
    """One synced campus-term, e.g. 2026-9-NB. Also the sync bookkeeping row."""

    __tablename__ = "terms"

    key: Mapped[str] = mapped_column(String(16), primary_key=True)  # "2026-9-NB"
    year: Mapped[int] = mapped_column(Integer)
    term: Mapped[str] = mapped_column(String(1))  # 0 winter, 1 spring, 7 summer, 9 fall
    campus: Mapped[str] = mapped_column(String(4))
    label: Mapped[str] = mapped_column(String(40))  # "Fall 2026 New Brunswick"
    synced_at: Mapped[str] = mapped_column(String(32))  # ISO 8601 UTC
    course_count: Mapped[int] = mapped_column(Integer, default=0)
    section_count: Mapped[int] = mapped_column(Integer, default=0)
    meeting_count: Mapped[int] = mapped_column(Integer, default=0)
    # Fingerprint of the *static* course data, so a re-sync that would change
    # nothing is skipped. Deliberately not the HTTP ETag: courses.json embeds
    # openStatus, so its ETag changes every cache window as seats flip even
    # when the catalog is untouched. See sync.content_fingerprint.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    courses: Mapped[list["Course"]] = relationship(
        back_populates="term_row", cascade="all, delete-orphan", passive_deletes=True
    )

    @staticmethod
    def make_key(year: int, term: str, campus: str) -> str:
        return f"{year}-{term}-{campus}"


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        # courseString alone is NOT unique: a course can have a supplementary
        # offering under the same number, e.g. 01:750:193 is a 4-credit lecture
        # ('  ') plus a separate 0-credit lab ('LB') students register for
        # independently. The supplement code is what separates them.
        UniqueConstraint(
            "term_key", "course_string", "supplement_code", name="uq_course_per_term"
        ),
        Index("ix_courses_term_subject", "term_key", "subject"),
        Index("ix_courses_term_level", "term_key", "level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term_key: Mapped[str] = mapped_column(
        String(16), ForeignKey("terms.key", ondelete="CASCADE"), index=True
    )
    course_string: Mapped[str] = mapped_column(String(16))  # "01:198:112"
    supplement_code: Mapped[str] = mapped_column(String(4), default="")  # "", "LB", "NB"
    subject: Mapped[str] = mapped_column(String(8), index=True)  # "198"
    subject_description: Mapped[str] = mapped_column(String(120))
    course_number: Mapped[str] = mapped_column(String(8))
    unit: Mapped[str] = mapped_column(String(8))
    school: Mapped[str] = mapped_column(String(160))
    level: Mapped[str] = mapped_column(String(1))  # U | G
    credits: Mapped[float | None] = mapped_column(Float, nullable=True)  # null = variable
    title: Mapped[str] = mapped_column(String(200), index=True)
    expanded_title: Mapped[str] = mapped_column(String(300), default="")
    prereq_notes: Mapped[str] = mapped_column(Text, default="")
    synopsis_url: Mapped[str] = mapped_column(Text, default="")
    campus_locations: Mapped[list] = mapped_column(JSON, default=list)

    term_row: Mapped[Term] = relationship(back_populates="courses")
    core_codes: Mapped[list["CourseCoreCode"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True
    )
    sections: Mapped[list["Section"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True
    )


class CourseCoreCode(Base):
    """Core curriculum requirement a course satisfies (HST, WCd, QQ, ...).

    Its own table rather than an array column so "courses satisfying HST" is an
    index hit — that is the query behind "fulfill 2 core requirements".
    """

    __tablename__ = "course_core_codes"
    __table_args__ = (
        UniqueConstraint("course_id", "code", name="uq_core_per_course"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(8), index=True)
    description: Mapped[str] = mapped_column(String(120), default="")

    course: Mapped[Course] = relationship(back_populates="core_codes")


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("course_id", "index", name="uq_section_per_course"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    # 5-digit registration index; unique within a term and what WebReg uses.
    index: Mapped[str] = mapped_column(String(8), index=True)
    number: Mapped[str] = mapped_column(String(8))  # "01"
    instructors: Mapped[list] = mapped_column(JSON, default=list)
    exam_code: Mapped[str] = mapped_column(String(4), default="")
    final_exam: Mapped[str] = mapped_column(String(64), default="")
    comments: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    open_to: Mapped[str] = mapped_column(Text, default="")  # major restrictions
    eligibility: Mapped[str] = mapped_column(String(120), default="")
    honors: Mapped[bool] = mapped_column(default=False)
    # Registration indexes of cross-listed twins — the same class under another
    # subject code. Never treat these as a time conflict with each other.
    cross_listed: Mapped[list] = mapped_column(JSON, default=list)

    course: Mapped[Course] = relationship(back_populates="sections")
    meetings: Mapped[list["Meeting"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", passive_deletes=True
    )


class Meeting(Base):
    """One weekly meeting block.

    Times are minutes since midnight and days are 0=Monday..6=Sunday, so the
    "nothing before 10am" and "no Friday classes" filters are integer
    comparisons the database can index. Asynchronous meetings carry NULL for
    day/start/end — they occupy no slot and can never conflict.
    """

    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_day_start", "day", "start_min"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(40), default="")  # LEC, RECIT, LAB, ...
    building: Mapped[str] = mapped_column(String(16), default="")
    room: Mapped[str] = mapped_column(String(16), default="")
    campus_code: Mapped[str] = mapped_column(String(4), default="")
    campus_name: Mapped[str] = mapped_column(String(40), default="")

    section: Mapped[Section] = relationship(back_populates="meetings")


class SectionStatus(Base):
    """Latest known open/closed state of one section, and when it last flipped.

    These three polling tables deliberately carry **no foreign key to terms**.
    ``sync.py`` replaces a term by deleting the row and letting the cascade
    take courses, sections, and meetings with it; a FK here would take the
    observation history along with them. Sections are referenced the way the
    rest of the system does it — by ``(term_key, index)``, the identifier that
    survives a re-sync.
    """

    __tablename__ = "section_status"

    term_key: Mapped[str] = mapped_column(String(16), primary_key=True)
    index: Mapped[str] = mapped_column(String(8), primary_key=True)
    is_open: Mapped[bool] = mapped_column(default=False)
    since: Mapped[str] = mapped_column(String(32))  # ISO 8601 UTC of last flip


class SectionStatusChange(Base):
    """Append-only log of every observed open/closed transition."""

    __tablename__ = "section_status_changes"
    __table_args__ = (
        Index("ix_status_changes_section", "term_key", "index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term_key: Mapped[str] = mapped_column(String(16), index=True)
    index: Mapped[str] = mapped_column(String(8))
    is_open: Mapped[bool] = mapped_column()
    at: Mapped[str] = mapped_column(String(32))  # ISO 8601 UTC


class PollRun(Base):
    """One row per poll tick, whether or not anything changed.

    Without this, a quiet stretch in the change log is ambiguous: it could
    mean nothing moved, or it could mean the poller was down. Any analysis of
    how fast sections fill needs to tell those apart.
    """

    __tablename__ = "poll_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term_key: Mapped[str] = mapped_column(String(16), index=True)
    at: Mapped[str] = mapped_column(String(32))
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    opened: Mapped[int] = mapped_column(Integer, default=0)
    closed: Mapped[int] = mapped_column(Integer, default=0)
    # Open indexes with no catalog row — the sign of a stale term sync.
    unknown: Mapped[int] = mapped_column(Integer, default=0)


class SavedSchedule(Base):
    """A generated schedule the user kept.

    Sections are referenced as (term_key, index) — never by row id, which a
    re-sync reassigns (see README). Storing the requirements and preference
    text alongside the result makes a saved schedule replayable: regenerating
    after the catalog changes is one POST with the stored inputs.
    """

    __tablename__ = "saved_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # No foreign key to terms, deliberately. A saved schedule has to outlive a
    # re-sync — that is why the requirements are stored alongside it, so it can
    # be regenerated. A plain FK would block the term delete that sync.py does,
    # and ON DELETE CASCADE would silently destroy the user's saved schedules
    # every time the catalog refreshed.
    term_key: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    indexes: Mapped[list] = mapped_column(JSON, default=list)  # ["10901", ...]
    requirements: Mapped[list] = mapped_column(JSON, default=list)
    preferences_text: Mapped[str] = mapped_column(Text, default="")
    constraints_json: Mapped[list] = mapped_column(JSON, default=list)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32))  # ISO 8601 UTC


def make_engine(url: str | None = None, echo: bool = False):
    engine = create_engine(url or database_url(), echo=echo, future=True)
    if engine.dialect.name == "sqlite":
        # SQLite ignores ON DELETE CASCADE unless foreign keys are enabled per
        # connection, and the default is off. Postgres enforces them natively,
        # so this only bites the local fallback — and only on the *second* sync
        # of a term: sync.py deletes the term row expecting courses to go with
        # it, they survive, and the rebuild dies on the uq_course_per_term
        # unique constraint.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine=None):
    return sessionmaker(bind=engine or make_engine(), future=True)


def create_all(engine=None) -> None:
    Base.metadata.create_all(engine or make_engine())
