"""Per-semester ingest of SOC course data into Postgres.

Pulls from ``courses.json`` only — the static half. ``openSections.json`` is
never touched here; open/closed is live state, overlaid at read time.

    python -m backend.class_scheduler.sync 2026 fall NB
    python -m backend.class_scheduler.sync 2026 fall NB NK CM
    python -m backend.class_scheduler.sync --list

A term is replaced wholesale rather than diffed: sections get added and pulled
between publication and add/drop, and at ~4.4k courses a full rewrite inside one
transaction is both faster and obviously correct compared to reconciling.

Because a re-sync assigns new primary keys, nothing outside this module should
store ``courses.id`` or ``sections.id``. Reference a section by
``(term_key, index)`` — the registration index is the stable identifier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import delete, select

from backend.class_scheduler.models import Course as ParsedCourse
from backend.class_scheduler.models import parse_courses
from backend.class_scheduler.schema import (
    Course,
    CourseCoreCode,
    Meeting,
    Section,
    Term,
    create_all,
    database_url,
    make_engine,
    make_session_factory,
)
from backend.class_scheduler.soc import CAMPUSES, TERMS, SOCClient, resolve_term

TERM_NAMES = {v: k.capitalize() for k, v in TERMS.items()}


def term_label(year: int, term: str, campus: str) -> str:
    return f"{TERM_NAMES.get(term, term)} {year} {CAMPUSES.get(campus, campus)}"


def content_fingerprint(courses: list[ParsedCourse]) -> str:
    """Hash of the static catalog, ignoring volatile open/closed state.

    The HTTP ETag cannot be used for this. ``courses.json`` embeds each
    section's ``openStatus``, so the response body — and therefore its ETag —
    changes every 15-minute cache window as seats open and close, even when no
    course, section or meeting has been touched. Hashing our own normalized
    projection with ``open`` excluded gives a value that moves only when the
    catalog really does.
    """
    digest = hashlib.sha256()
    for course in sorted(courses, key=lambda c: (c.course_string, c.supplement)):
        payload = course.model_dump(exclude={"sections"})
        digest.update(json.dumps(payload, sort_keys=True, default=str).encode())
        for section in sorted(course.sections, key=lambda s: s.index):
            digest.update(
                json.dumps(
                    section.model_dump(exclude={"open"}), sort_keys=True, default=str
                ).encode()
            )
    return digest.hexdigest()


def sync_term(
    session,
    year: int,
    term: str,
    campus: str = "NB",
    client: SOCClient | None = None,
    force: bool = False,
) -> Term:
    """Replace one campus-term's static data. Returns the Term bookkeeping row."""
    key = Term.make_key(year, term, campus)
    existing = session.get(Term, key)

    started = time.time()
    client = client or SOCClient()
    raw = client.courses(year, term, campus)
    courses = parse_courses(raw)  # no open-index overlay: that state is not stored
    fingerprint = content_fingerprint(courses)
    print(f"  {key}: fetched {len(courses)} courses in {time.time() - started:.1f}s")

    # The fingerprint needs the full download anyway (there is no cheap upstream
    # freshness probe), but skipping the rewrite keeps re-runs safe and quiet.
    if existing and not force and existing.content_hash == fingerprint:
        print(f"  {key}: catalog unchanged since {existing.synced_at}, skipping write")
        return existing

    # Cascades clear courses/core codes/sections/meetings for this term.
    if existing:
        session.execute(delete(Term).where(Term.key == key))
        session.flush()

    term_row = Term(
        key=key,
        year=year,
        term=term,
        campus=campus,
        label=term_label(year, term, campus),
        synced_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        content_hash=fingerprint,
    )
    session.add(term_row)
    session.flush()

    n_sections = n_meetings = 0
    for course in courses:
        row = Course(
            term_key=key,
            course_string=course.course_string,
            supplement_code=course.supplement,
            subject=course.subject,
            subject_description=course.subject_description,
            course_number=course.course_number,
            unit=course.unit,
            school=course.school,
            level=course.level,
            credits=course.credits,
            title=course.title,
            expanded_title=course.expanded_title,
            prereq_notes=course.prereq_notes,
            synopsis_url=course.synopsis_url,
            campus_locations=course.campus_locations,
        )
        row.core_codes = [
            CourseCoreCode(
                code=code,
                description=course.core_code_descriptions.get(code, ""),
            )
            # The API repeats a code when a course satisfies it under several
            # units; the unique constraint would reject the duplicate.
            for code in dict.fromkeys(course.core_codes)
            if code
        ]
        for section in course.sections:
            section_row = Section(
                index=section.index,
                number=section.number,
                instructors=section.instructors,
                exam_code=section.exam_code,
                final_exam=section.final_exam,
                comments=section.comments,
                notes=section.notes,
                open_to=section.open_to,
                eligibility=section.eligibility,
                honors=section.honors,
                cross_listed=section.cross_listed,
            )
            section_row.meetings = [
                Meeting(
                    day=m.day,
                    start_min=m.start,
                    end_min=m.end,
                    mode=m.mode,
                    building=m.building,
                    room=m.room,
                    campus_code=m.campus_code,
                    campus_name=m.campus_name,
                )
                for m in section.meetings
            ]
            n_meetings += len(section_row.meetings)
            n_sections += 1
            row.sections.append(section_row)
        session.add(row)

    term_row.course_count = len(courses)
    term_row.section_count = n_sections
    term_row.meeting_count = n_meetings

    session.commit()
    print(
        f"  {key}: wrote {len(courses)} courses / {n_sections} sections / "
        f"{n_meetings} meetings in {time.time() - started:.1f}s"
    )
    return term_row


def list_terms(session) -> None:
    rows = session.execute(select(Term).order_by(Term.key)).scalars().all()
    if not rows:
        print("no terms synced yet")
        return
    print(f"{'key':<14}{'label':<32}{'courses':>9}{'sections':>10}{'meetings':>10}  synced")
    for r in rows:
        print(
            f"{r.key:<14}{r.label:<32}{r.course_count:>9}{r.section_count:>10}"
            f"{r.meeting_count:>10}  {r.synced_at}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", nargs="?", type=int, help="e.g. 2026")
    parser.add_argument("term", nargs="?", help="fall | spring | summer | winter (or 9/1/7/0)")
    parser.add_argument("campuses", nargs="*", default=None, help="NB NK CM (default NB)")
    parser.add_argument("--force", action="store_true", help="re-sync even if the ETag matches")
    parser.add_argument("--list", action="store_true", help="show synced terms and exit")
    args = parser.parse_args()

    engine = make_engine()
    create_all(engine)
    session = make_session_factory(engine)()
    print(f"database: {database_url()}")

    try:
        if args.list:
            list_terms(session)
            return 0

        if args.year is None or args.term is None:
            parser.error("year and term are required unless --list is given")

        term = resolve_term(args.term)
        campuses = args.campuses or ["NB"]
        client = SOCClient()
        for campus in campuses:
            sync_term(session, args.year, term, campus, client=client, force=args.force)

        print()
        list_terms(session)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
