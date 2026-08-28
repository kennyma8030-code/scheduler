"""Requirement models and the DB query layer feeding the generator.

Requirements are the user's input, and their ``kind`` IS the lock level:

    section   exact WebReg index — a group of one candidate (the skeleton)
    course    course fixed, generator picks the section
    one_of    generator picks course AND section from the listed options
    core      generator picks any course satisfying a core code

Catalog reads hit the synced database (see schema.py / sync.py), never the
SOC API; only the live open-status overlay touches ``SOCClient``, whose 30s
disk cache makes that effectively free.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.class_scheduler import models, schema
from backend.class_scheduler.generator import Candidate, Group
from backend.class_scheduler.soc import SOCClient


class CourseRef(BaseModel):
    course_string: str
    supplement: str = ""


class Requirement(BaseModel):
    kind: Literal["section", "course", "one_of", "core"]
    course_string: str | None = None      # section | course
    supplement: str = ""
    index: str | None = None              # section: exact WebReg index
    options: list[CourseRef] | None = None  # one_of
    core_code: str | None = None          # core
    subjects: list[str] | None = None     # core: optional narrowing
    level: str = "U"
    label: str = ""

    def display_label(self) -> str:
        if self.label:
            return self.label
        if self.kind == "section":
            return f"{self.course_string} idx {self.index}"
        if self.kind == "course":
            return self.course_string or "course"
        if self.kind == "one_of":
            return "one of: " + ", ".join(o.course_string for o in self.options or [])
        return f"core {self.core_code}"


class GenerateOptions(BaseModel):
    open_only: bool = True
    assumed_credits_for_variable: float = 3.0
    max_course_combos: int = 5
    max_sections_per_combo: int = 5
    time_budget_s: float | None = None


class CatalogError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# ORM -> normalized pydantic models


def _orm_to_course(row: schema.Course) -> models.Course:
    return models.Course(
        course_string=row.course_string,
        supplement=row.supplement_code,
        title=row.title,
        expanded_title=row.expanded_title,
        subject=row.subject,
        subject_description=row.subject_description,
        course_number=row.course_number,
        unit=row.unit,
        school=row.school,
        level=row.level,
        credits=row.credits,
        core_codes=[c.code for c in row.core_codes],
        core_code_descriptions={c.code: c.description for c in row.core_codes},
        prereq_notes=row.prereq_notes,
        synopsis_url=row.synopsis_url,
        campus_locations=list(row.campus_locations or []),
        sections=[
            models.Section(
                index=s.index,
                number=s.number,
                open=False,  # overlaid from openSections.json by the caller
                instructors=list(s.instructors or []),
                meetings=[
                    models.Meeting(
                        day=m.day,
                        start=m.start_min,
                        end=m.end_min,
                        mode=m.mode,
                        building=m.building,
                        room=m.room,
                        campus_code=m.campus_code,
                        campus_name=m.campus_name,
                    )
                    for m in s.meetings
                ],
                exam_code=s.exam_code,
                final_exam=s.final_exam,
                comments=s.comments,
                notes=s.notes,
                open_to=s.open_to,
                eligibility=s.eligibility,
                honors=s.honors,
                cross_listed=list(s.cross_listed or []),
            )
            for s in row.sections
        ],
    )


_COURSE_LOAD = (
    selectinload(schema.Course.sections).selectinload(schema.Section.meetings),
    selectinload(schema.Course.core_codes),
)


def load_course(
    session: Session, term_key: str, course_string: str, supplement: str = ""
) -> models.Course | None:
    row = session.execute(
        select(schema.Course)
        .where(
            schema.Course.term_key == term_key,
            schema.Course.course_string == course_string,
            schema.Course.supplement_code == supplement,
        )
        .options(*_COURSE_LOAD)
    ).scalar_one_or_none()
    return _orm_to_course(row) if row else None


def load_core_courses(
    session: Session,
    term_key: str,
    core_code: str,
    subjects: list[str] | None = None,
    level: str = "U",
) -> list[models.Course]:
    query = (
        select(schema.Course)
        .join(schema.CourseCoreCode)
        .where(
            schema.Course.term_key == term_key,
            schema.CourseCoreCode.code == core_code,
        )
        .options(*_COURSE_LOAD)
    )
    if level:
        query = query.where(schema.Course.level == level)
    if subjects:
        query = query.where(schema.Course.subject.in_(subjects))
    rows = session.execute(query).scalars().unique().all()
    return [_orm_to_course(r) for r in rows]


def open_indexes_for(term_key: str, client: SOCClient | None = None) -> set[str]:
    """Live open-section overlay for a term key like '2026-9-NB'."""
    year, term, campus = term_key.split("-")
    client = client or SOCClient()
    return client.open_section_indexes(int(year), term, campus)


def apply_open_overlay(courses: list[models.Course], open_indexes: set[str]) -> None:
    for course in courses:
        for section in course.sections:
            section.open = section.index in open_indexes


# ---------------------------------------------------------------------------
# requirements -> generator groups


def build_groups(
    session: Session,
    term_key: str,
    requirements: list[Requirement],
    open_indexes: set[str] | None = None,
) -> tuple[list[Group], dict | None]:
    """Returns (groups, infeasible). Groups carry candidates with the open
    overlay already applied; hard filtering and caps happen in the generator."""
    groups: list[Group] = []
    seen_courses: list[models.Course] = []

    for req in requirements:
        label = req.display_label()

        if req.kind in ("section", "course"):
            if not req.course_string:
                return [], {"group": label, "reason": "missing course_string"}
            course = load_course(session, term_key, req.course_string, req.supplement)
            if course is None:
                return [], {
                    "group": label,
                    "reason": f"{req.course_string} not found in {term_key}",
                }
            courses = [course]
        elif req.kind == "one_of":
            courses = []
            for ref in req.options or []:
                course = load_course(session, term_key, ref.course_string, ref.supplement)
                if course is not None:
                    courses.append(course)
            if not courses:
                return [], {"group": label, "reason": "none of the options exist in this term"}
        else:  # core
            if not req.core_code:
                return [], {"group": label, "reason": "missing core_code"}
            courses = load_core_courses(
                session, term_key, req.core_code, req.subjects, req.level
            )
            if not courses:
                return [], {
                    "group": label,
                    "reason": f"no {req.level}-level courses satisfy core {req.core_code}",
                }

        if open_indexes is not None:
            apply_open_overlay(courses, open_indexes)
        seen_courses.extend(courses)

        if req.kind == "section":
            match = next(
                (
                    (c, s)
                    for c in courses
                    for s in c.sections
                    if s.index == req.index
                ),
                None,
            )
            if match is None:
                return [], {
                    "group": label,
                    "reason": f"index {req.index} not found under {req.course_string}",
                }
            candidates = [Candidate.build(match[0], match[1], len(groups))]
            groups.append(Group(label, candidates, locked=True))
            continue

        candidates = [
            Candidate.build(course, section, len(groups))
            for course in courses
            for section in course.sections
        ]
        if not candidates:
            return [], {"group": label, "reason": "no sections exist"}
        groups.append(
            Group(label, candidates, flexible=req.kind in ("one_of", "core"))
        )

    return groups, None


def context_courses(groups: list[Group]) -> list[models.Course]:
    """Distinct courses across groups, for the constraint factory's context."""
    seen: dict[tuple[str, str], models.Course] = {}
    for group in groups:
        for cand in group.candidates:
            seen.setdefault((cand.course.course_string, cand.course.supplement), cand.course)
    return list(seen.values())
