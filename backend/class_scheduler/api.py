"""HTTP surface of the course scheduler: catalog reads, generation, saving.

Everything the frontend needs proxies through here — the SOC API has no CORS,
so the browser never talks to Rutgers directly. Catalog reads hit the synced
database; only the open-status overlay touches ``SOCClient`` (30-second disk
cache, serves stale on outage).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.class_scheduler import catalog, schema
from backend.class_scheduler.constraints import (
    CatalogContext,
    build_constraints,
    default_constraints,
)
from backend.class_scheduler.generator import CourseScheduleGenerator
from backend.class_scheduler.models import CAMPUS_LOCATIONS
from backend.class_scheduler.preference_parser import (
    CoursePreferenceParser,
    ParserUnavailable,
)
from backend.class_scheduler.soc import SOCClient, SOCError

router = APIRouter(prefix="/api")

_engine = None
_session_factory = None
_soc_client = SOCClient()


def _session():
    global _engine, _session_factory
    if _session_factory is None:
        _engine = schema.make_engine()
        schema.create_all(_engine)
        _session_factory = schema.make_session_factory(_engine)
    return _session_factory()


def _term_or_404(session, term_key: str) -> schema.Term:
    term = session.get(schema.Term, term_key)
    if term is None:
        raise HTTPException(404, f"term {term_key} is not synced")
    return term


def _open_indexes(term_key: str) -> set[str]:
    try:
        return catalog.open_indexes_for(term_key, _soc_client)
    except (SOCError, ValueError):
        return set()  # degraded: everything shows closed rather than erroring


# ---------------------------------------------------------------------------
# catalog reads


@router.get("/terms")
def list_terms():
    with _session() as session:
        rows = session.execute(
            select(schema.Term).order_by(schema.Term.key.desc())
        ).scalars().all()
        return [
            {
                "key": t.key,
                "label": t.label,
                "course_count": t.course_count,
                "section_count": t.section_count,
                "synced_at": t.synced_at,
            }
            for t in rows
        ]


@router.get("/subjects")
def list_subjects(term_key: str):
    with _session() as session:
        _term_or_404(session, term_key)
        rows = session.execute(
            select(
                schema.Course.subject,
                schema.Course.subject_description,
                func.count(schema.Course.id),
            )
            .where(schema.Course.term_key == term_key)
            .group_by(schema.Course.subject, schema.Course.subject_description)
            .order_by(schema.Course.subject)
        ).all()
        return [
            {"code": code, "description": desc, "course_count": count}
            for code, desc, count in rows
        ]


@router.get("/core-codes")
def list_core_codes(term_key: str):
    with _session() as session:
        _term_or_404(session, term_key)
        rows = session.execute(
            select(
                schema.CourseCoreCode.code,
                func.max(schema.CourseCoreCode.description),
                func.count(schema.CourseCoreCode.id),
            )
            .join(schema.Course)
            .where(schema.Course.term_key == term_key)
            .group_by(schema.CourseCoreCode.code)
            .order_by(func.count(schema.CourseCoreCode.id).desc())
        ).all()
        return [
            {"code": code, "description": desc, "course_count": count}
            for code, desc, count in rows
        ]


def _normalize_query(q: str) -> str:
    """'cs 112' and '198:112' should both find 01:198:112."""
    return q.strip()


@router.get("/courses/search")
def search_courses(term_key: str, q: str = "", subject: str = "",
                   core: str = "", level: str = "U", limit: int = 20):
    limit = max(1, min(50, limit))
    with _session() as session:
        _term_or_404(session, term_key)
        query = (
            select(schema.Course)
            .where(schema.Course.term_key == term_key)
            .order_by(schema.Course.course_string, schema.Course.supplement_code)
        )
        if level:
            query = query.where(schema.Course.level == level)
        if subject:
            query = query.where(schema.Course.subject == subject)
        if core:
            query = query.join(schema.CourseCoreCode).where(
                schema.CourseCoreCode.code == core
            )
        text = _normalize_query(q)
        if text:
            pattern = f"%{text}%"
            query = query.where(
                schema.Course.course_string.like(pattern)
                | schema.Course.title.ilike(pattern)
                | schema.Course.expanded_title.ilike(pattern)
            )
        rows = session.execute(query.limit(limit)).scalars().unique().all()

        open_indexes = _open_indexes(term_key)
        results = []
        for row in rows:
            section_indexes = [s.index for s in row.sections]
            campuses = sorted({
                m.campus_code for s in row.sections for m in s.meetings
                if m.campus_code in CAMPUS_LOCATIONS
            })
            results.append({
                "course_string": row.course_string,
                "supplement": row.supplement_code,
                "title": row.expanded_title or row.title,
                "credits": row.credits,
                "core_codes": sorted({c.code for c in row.core_codes}),
                "section_count": len(section_indexes),
                "open_section_count": sum(
                    1 for i in section_indexes if i in open_indexes
                ),
                "campuses": campuses,
                "has_async_sections": any(
                    all(m.day is None for m in s.meetings) for s in row.sections
                ),
            })
        return results


@router.get("/courses/{term_key}/{course_string}")
def course_detail(term_key: str, course_string: str, supplement: str = ""):
    with _session() as session:
        _term_or_404(session, term_key)
        course = catalog.load_course(session, term_key, course_string, supplement)
        if course is None:
            raise HTTPException(404, f"{course_string} not found in {term_key}")
        catalog.apply_open_overlay([course], _open_indexes(term_key))
        return {
            "course_string": course.course_string,
            "supplement": course.supplement,
            "title": course.expanded_title or course.title,
            "subject": course.subject,
            "subject_description": course.subject_description,
            "credits": course.credits,
            "level": course.level,
            "core_codes": course.core_codes,
            "prereq_notes": course.prereq_notes,
            "synopsis_url": course.synopsis_url,
            "sections": [
                {
                    "index": s.index,
                    "number": s.number,
                    "open": s.open,
                    "instructors": s.instructors,
                    "honors": s.honors,
                    "exam_code": s.exam_code,
                    "final_exam": s.final_exam,
                    "comments": s.comments,
                    "meetings": [
                        {
                            "day": m.day,
                            "start": m.start,
                            "end": m.end,
                            "mode": m.mode,
                            "building": m.building,
                            "room": m.room,
                            "campus_code": m.campus_code,
                            "campus_name": m.campus_name,
                        }
                        for m in s.meetings
                    ],
                }
                for s in course.sections
            ],
        }


@router.get("/open-status")
def open_status(term_key: str):
    indexes = _open_indexes(term_key)
    return {
        "open_indexes": sorted(indexes),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# generation


class GenerateRequest(BaseModel):
    term_key: str
    requirements: list[catalog.Requirement]
    preferences_text: str = ""
    options: catalog.GenerateOptions = catalog.GenerateOptions()


@router.post("/schedule/generate")
def generate_schedule(body: GenerateRequest):
    if not 1 <= len(body.requirements) <= 8:
        raise HTTPException(422, "between 1 and 8 requirements")
    with _session() as session:
        _term_or_404(session, body.term_key)
        open_indexes = _open_indexes(body.term_key)
        groups, infeasible = catalog.build_groups(
            session, body.term_key, body.requirements, open_indexes
        )
        if infeasible:
            return {
                "course_combos": [], "results": [], "stats": {},
                "warnings": [], "constraints": [], "infeasible": infeasible,
            }

        core_rows = session.execute(
            select(
                schema.CourseCoreCode.code,
                func.max(schema.CourseCoreCode.description),
            )
            .join(schema.Course)
            .where(schema.Course.term_key == body.term_key)
            .group_by(schema.CourseCoreCode.code)
        ).all()
        core_codes = {code: desc for code, desc in core_rows}

    ctx = CatalogContext(
        courses=catalog.context_courses(groups),
        valid_core_codes=set(core_codes),
        assumed_credits=body.options.assumed_credits_for_variable,
    )
    warnings: list[str] = []
    raw_constraints: list[dict] = []
    if body.preferences_text.strip():
        try:
            raw_constraints = CoursePreferenceParser().parse(
                body.preferences_text, ctx.courses, core_codes
            )
        except ParserUnavailable:
            warnings.append(
                "preference parsing is unavailable (no GEMINI_API_KEY) — "
                "generated without your text preferences"
            )
        except Exception as exc:  # noqa: BLE001 — degrade, don't 500
            warnings.append(f"preference parsing failed ({exc}) — "
                            "generated without your text preferences")
    constraints, factory_warnings = build_constraints(raw_constraints, ctx)
    warnings.extend(factory_warnings)
    constraints.extend(default_constraints(open_only=body.options.open_only))

    generator = CourseScheduleGenerator(
        groups,
        constraints,
        max_course_combos=body.options.max_course_combos,
        max_sections_per_combo=body.options.max_sections_per_combo,
        assumed_credits=body.options.assumed_credits_for_variable,
        time_budget_s=body.options.time_budget_s,
    )
    out = generator.run()
    out["warnings"] = warnings + out["warnings"]
    out["constraints"] = raw_constraints
    # What the generator actually ran with: the parsed preferences that
    # survived the factory, plus the defaults injected on every request. The
    # raw LLM output above is neither — it omits the defaults and still lists
    # anything that was dropped.
    out["applied_constraints"] = [c.describe() for c in constraints]
    return out


# ---------------------------------------------------------------------------
# persistence


class SaveRequest(BaseModel):
    term_key: str
    name: str = ""
    indexes: list[str]
    requirements: list[catalog.Requirement] = []
    preferences_text: str = ""
    constraints_json: list[dict] = []
    score: float | None = None


@router.post("/schedule/save")
def save_schedule(body: SaveRequest):
    with _session() as session:
        _term_or_404(session, body.term_key)
        row = schema.SavedSchedule(
            term_key=body.term_key,
            name=body.name,
            indexes=body.indexes,
            requirements=[r.model_dump() for r in body.requirements],
            preferences_text=body.preferences_text,
            constraints_json=body.constraints_json,
            score=body.score,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        session.add(row)
        session.commit()
        return {"id": row.id}


@router.get("/schedule/saved")
def list_saved():
    with _session() as session:
        rows = session.execute(
            select(schema.SavedSchedule).order_by(schema.SavedSchedule.id.desc())
        ).scalars().all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "term_key": r.term_key,
                "score": r.score,
                "indexes": r.indexes,
                "created_at": r.created_at,
            }
            for r in rows
        ]


@router.get("/schedule/saved/{saved_id}")
def load_saved(saved_id: int):
    with _session() as session:
        row = session.get(schema.SavedSchedule, saved_id)
        if row is None:
            raise HTTPException(404, "no such saved schedule")

        open_indexes = _open_indexes(row.term_key)
        wanted = set(row.indexes or [])
        sections = session.execute(
            select(schema.Section)
            .join(schema.Course)
            .where(
                schema.Course.term_key == row.term_key,
                schema.Section.index.in_(wanted),
            )
        ).scalars().unique().all()

        found: list[dict] = []
        for s in sections:
            found.append({
                "course_string": s.course.course_string,
                "title": s.course.expanded_title or s.course.title,
                "credits": s.course.credits,
                "section": {
                    "index": s.index,
                    "number": s.number,
                    "open": s.index in open_indexes,
                    "instructors": s.instructors,
                    "honors": s.honors,
                    "exam_code": s.exam_code,
                    "final_exam": s.final_exam,
                    "meetings": [
                        {
                            "day": m.day, "start": m.start_min, "end": m.end_min,
                            "mode": m.mode, "building": m.building, "room": m.room,
                            "campus_code": m.campus_code,
                        }
                        for m in s.meetings
                    ],
                },
            })
        return {
            "id": row.id,
            "name": row.name,
            "term_key": row.term_key,
            "score": row.score,
            "preferences_text": row.preferences_text,
            "requirements": row.requirements,
            "constraints_json": row.constraints_json,
            "selections": found,
            # Indexes that vanished in a re-sync — the section no longer exists.
            "stale_indexes": sorted(wanted - {s.index for s in sections}),
            "created_at": row.created_at,
        }
