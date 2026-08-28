"""Constraint vocabulary for the course schedule generator.

Three kinds, sharing the contract the roommate optimizer proved out — every
constraint scores in [0.0, 1.0] where 0 is "no violation", carries a weight,
and a hard constraint with any score > 0 rejects the schedule outright:

    section     decomposable per (course, section) candidate. Precomputed once
                per candidate; hard ones act as *filters* before search.
    schedule    needs the merged week of meeting blocks (gaps, spans, days).
    selection   about the chosen set of courses, ignoring times (credits,
                core coverage, final exams).

Formulas work directly on meeting blocks (minutes since midnight), never on
per-slot loops — a five-course week is ~15 intervals, not 7x288 ticks.

``build_constraints`` is the factory that turns LLM-emitted JSON into
constraint objects, repairing what it can and *recording* what it drops —
the one deliberate improvement over the old constraint_factory's silent
drops.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from backend.timegrid import BREAK_MIN_MINUTES, MINUTES_PER_DAY
from backend.class_scheduler.models import CAMPUS_LOCATIONS, DAY_NAMES, Course
from backend.class_scheduler import travel


# ---------------------------------------------------------------------------
# base classes


class BaseConstraint:
    kind = "section"
    type_name = ""

    def __init__(self, hard: bool = False, weight: float = 0.5):
        self.hard = bool(hard)
        self.weight = max(0.0, min(1.0, float(weight)))

    def describe(self) -> dict:
        return {"type": self.type_name, "hard": self.hard, "weight": self.weight}


class SectionConstraint(BaseConstraint):
    kind = "section"

    def score_section(self, cand) -> float:  # cand: generator.Candidate
        raise NotImplementedError


class ScheduleConstraint(BaseConstraint):
    kind = "schedule"

    def score_schedule(self, week) -> float:  # week: generator.WeekOccupancy
        raise NotImplementedError


class SelectionConstraint(BaseConstraint):
    kind = "selection"

    def score_selection(self, selection) -> float:  # list[generator.Candidate]
        raise NotImplementedError


# ---------------------------------------------------------------------------
# helpers


def _timed_blocks(cand, days=None):
    if days is None:
        return cand.blocks
    return [b for b in cand.blocks if b.day in days]


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.casefold())


def _surname(name: str) -> str:
    """SOC instructor format is 'SURNAME, INITIAL' — the surname is the part
    before the comma."""
    return _norm_name(name.split(",")[0])


def _name_tokens(name: str) -> set[str]:
    """User-side names arrive freeform ('Professor Centeno', 'centeno, j') —
    any word could be the surname."""
    return set(re.findall(r"[a-z]+", str(name).casefold()))


def _instructor_match(section_instructors: list[str], names: list[str]) -> bool:
    surnames = {_surname(i) for i in section_instructors} - {""}
    return any(surnames & _name_tokens(n) for n in names if n)


# ---------------------------------------------------------------------------
# section-kind


class NoClassesBefore(SectionConstraint):
    type_name = "no_classes_before"

    def __init__(self, time: int, days: list[int] | None = None, **kw):
        super().__init__(**kw)
        self.time = int(time)
        self.days = set(days) if days else None

    def score_section(self, cand) -> float:
        blocks = _timed_blocks(cand, self.days)
        if not blocks:
            return 0.0
        return sum(1 for b in blocks if b.start < self.time) / len(blocks)


class NoClassesAfter(SectionConstraint):
    type_name = "no_classes_after"

    def __init__(self, time: int, days: list[int] | None = None, **kw):
        super().__init__(**kw)
        self.time = int(time)
        self.days = set(days) if days else None

    def score_section(self, cand) -> float:
        blocks = _timed_blocks(cand, self.days)
        if not blocks:
            return 0.0
        return sum(1 for b in blocks if b.end > self.time) / len(blocks)


class NoClassesOnDays(SectionConstraint):
    type_name = "no_classes_on_days"

    def __init__(self, days: list[int], **kw):
        super().__init__(**kw)
        self.days = set(days)

    def score_section(self, cand) -> float:
        if not cand.blocks:
            return 0.0
        return sum(1 for b in cand.blocks if b.day in self.days) / len(cand.blocks)


class AvoidEarlyMornings(NoClassesBefore):
    """Its own LLM label for the "no 8ams" idiom; defaults to before-9:00."""

    type_name = "avoid_early_mornings"

    def __init__(self, time: int = 9 * 60, days: list[int] | None = None, **kw):
        super().__init__(time=time, days=days, **kw)


class PreferInstructor(SectionConstraint):
    type_name = "prefer_instructor"

    def __init__(self, course_string: str, names: list[str], **kw):
        super().__init__(**kw)
        self.course_string = course_string
        self.names = names

    def score_section(self, cand) -> float:
        if cand.course.course_string != self.course_string:
            return 0.0
        return 0.0 if _instructor_match(cand.section.instructors, self.names) else 1.0


class AvoidInstructor(SectionConstraint):
    type_name = "avoid_instructor"

    def __init__(self, names: list[str], course_string: str | None = None, **kw):
        super().__init__(**kw)
        self.course_string = course_string
        self.names = names

    def score_section(self, cand) -> float:
        if self.course_string and cand.course.course_string != self.course_string:
            return 0.0
        return 1.0 if _instructor_match(cand.section.instructors, self.names) else 0.0


class OpenSectionsOnly(SectionConstraint):
    type_name = "open_sections_only"

    def __init__(self, hard: bool = True, weight: float = 1.0):
        super().__init__(hard=hard, weight=weight)

    def score_section(self, cand) -> float:
        return 0.0 if cand.section.open else 1.0


class PreferAsync(SectionConstraint):
    type_name = "prefer_async"

    def __init__(self, maximize: bool = True, **kw):
        super().__init__(**kw)
        self.maximize = bool(maximize)

    def score_section(self, cand) -> float:
        meetings = cand.section.meetings
        if not meetings:
            return 0.0 if self.maximize else 1.0
        mismatched = sum(
            1 for m in meetings if m.is_async != self.maximize
        )
        return mismatched / len(meetings)


class PreferCampus(SectionConstraint):
    type_name = "prefer_campus"

    def __init__(self, campus_codes: list[str], **kw):
        super().__init__(**kw)
        self.campus_codes = set(campus_codes)

    def score_section(self, cand) -> float:
        if not cand.blocks:
            return 0.0
        off = sum(1 for b in cand.blocks if b.campus_code not in self.campus_codes)
        return off / len(cand.blocks)


class AvoidCampus(SectionConstraint):
    type_name = "avoid_campus"

    def __init__(self, campus_codes: list[str], **kw):
        super().__init__(**kw)
        self.campus_codes = set(campus_codes)

    def score_section(self, cand) -> float:
        if not cand.blocks:
            return 0.0
        on = sum(1 for b in cand.blocks if b.campus_code in self.campus_codes)
        return on / len(cand.blocks)


class PreferHonors(SectionConstraint):
    type_name = "prefer_honors"

    def score_section(self, cand) -> float:
        return 0.0 if cand.section.honors else 1.0


class AvoidHonors(SectionConstraint):
    type_name = "avoid_honors"

    def score_section(self, cand) -> float:
        return 1.0 if cand.section.honors else 0.0


# ---------------------------------------------------------------------------
# schedule-kind


class MaxDaysWithClasses(ScheduleConstraint):
    type_name = "max_days_with_classes"

    def __init__(self, max_days: int, **kw):
        super().__init__(**kw)
        self.max_days = int(max_days)

    def score_schedule(self, week) -> float:
        used = sum(1 for day in week.days if day)
        excess = max(0, used - self.max_days)
        return excess / max(1, 7 - self.max_days)


class FreeDayOn(ScheduleConstraint):
    type_name = "free_day_on"

    def __init__(self, days: list[int], **kw):
        super().__init__(**kw)
        self.days = sorted(set(days))

    def score_schedule(self, week) -> float:
        if not self.days:
            return 0.0
        busy = sum(1 for d in self.days if week.days[d])
        return busy / len(self.days)


class MaxGapPerDay(ScheduleConstraint):
    type_name = "max_gap_per_day"

    def __init__(self, max_gap: int, ignore_below: int = BREAK_MIN_MINUTES, **kw):
        super().__init__(**kw)
        self.max_gap = int(max_gap)
        self.ignore_below = int(ignore_below)

    def score_schedule(self, week) -> float:
        day_scores = []
        for blocks in week.days:
            if not blocks:
                continue
            excess = 0
            for a, b in zip(blocks, blocks[1:]):
                gap = b.start - a.end
                # Sub-30-minute holes are passing periods, not gaps.
                if gap < self.ignore_below:
                    continue
                excess += max(0, gap - self.max_gap)
            day_scores.append(min(1.0, excess / MINUTES_PER_DAY))
        return sum(day_scores) / len(day_scores) if day_scores else 0.0


class CompactDays(ScheduleConstraint):
    type_name = "compact_days"

    def __init__(self, tight: bool = True, **kw):
        super().__init__(**kw)
        self.tight = bool(tight)

    def score_schedule(self, week) -> float:
        ratios = []
        for blocks in week.days:
            if not blocks:
                continue
            span = blocks[-1].end - blocks[0].start
            if span <= 0:
                continue
            busy = sum(b.end - b.start for b in blocks)
            idle = max(0, span - busy)
            ratios.append(idle / span)
        if not ratios:
            return 0.0
        mean = sum(ratios) / len(ratios)
        return mean if self.tight else 1.0 - mean


class LunchBreak(ScheduleConstraint):
    type_name = "lunch_break"

    def __init__(self, window: tuple[int, int] = (11 * 60, 14 * 60),
                 min_free: int = 30, **kw):
        super().__init__(**kw)
        self.window = (int(window[0]), int(window[1]))
        self.min_free = int(min_free)

    def score_schedule(self, week) -> float:
        lo, hi = self.window
        class_days = 0
        lacking = 0
        for blocks in week.days:
            if not blocks:
                continue
            class_days += 1
            # Longest free run inside the window, given blocks clipped to it.
            cursor = lo
            best = 0
            for b in blocks:
                if b.end <= lo or b.start >= hi:
                    continue
                best = max(best, b.start - cursor)
                cursor = max(cursor, b.end)
            best = max(best, hi - cursor)
            if best < self.min_free:
                lacking += 1
        return lacking / class_days if class_days else 0.0


class GetOutBy(ScheduleConstraint):
    type_name = "get_out_by"

    def __init__(self, time: int, days: list[int] | None = None, **kw):
        super().__init__(**kw)
        self.time = int(time)
        self.days = set(days) if days else None

    def score_schedule(self, week) -> float:
        scores = []
        for day, blocks in enumerate(week.days):
            if not blocks or (self.days is not None and day not in self.days):
                continue
            overrun = max(0, blocks[-1].end - self.time)
            scores.append(min(1.0, overrun / 120))
        return sum(scores) / len(scores) if scores else 0.0


class MaxClassesPerDay(ScheduleConstraint):
    type_name = "max_classes_per_day"

    def __init__(self, max_count: int, **kw):
        super().__init__(**kw)
        self.max_count = int(max_count)

    def score_schedule(self, week) -> float:
        worst = max((len(blocks) for blocks in week.days), default=0)
        excess = max(0, worst - self.max_count)
        return min(1.0, excess / max(1, self.max_count))


class TravelComfort(ScheduleConstraint):
    """Soft campus-hop comfort. The hard 35-minute rule lives in the
    generator's conflict mask, not here."""

    type_name = "travel_comfort"

    def __init__(self, slack: int = 10, **kw):
        super().__init__(**kw)
        self.slack = int(slack)

    def score_schedule(self, week) -> float:
        violations = []
        for blocks in week.days:
            for a, b in zip(blocks, blocks[1:]):
                if not travel.needs_transfer(a.campus_code, b.campus_code):
                    continue
                need = travel.travel_minutes(a.campus_code, b.campus_code) + self.slack
                gap = max(0, b.start - a.end)
                violations.append(max(0.0, need - gap) / need)
        return sum(violations) / len(violations) if violations else 0.0


# ---------------------------------------------------------------------------
# selection-kind


class CreditRange(SelectionConstraint):
    type_name = "credit_range"

    def __init__(self, min_credits: float | None = None,
                 max_credits: float | None = None,
                 assumed_credits: float = 3.0, **kw):
        super().__init__(**kw)
        self.min_credits = min_credits
        self.max_credits = max_credits
        self.assumed_credits = assumed_credits

    def total(self, selection) -> float:
        return sum(
            c.credits if c.credits is not None else self.assumed_credits
            for c in selection
        )

    def score_selection(self, selection) -> float:
        total = self.total(selection)
        deviation = 0.0
        if self.min_credits is not None:
            deviation += max(0.0, self.min_credits - total)
        if self.max_credits is not None:
            deviation += max(0.0, total - self.max_credits)
        # One 3-credit course of deviation saturates the violation.
        return min(1.0, deviation / 3.0)


class CoreCoverage(SelectionConstraint):
    type_name = "core_coverage"

    def __init__(self, codes: list[str], count: int | None = None, **kw):
        super().__init__(**kw)
        self.codes = [c.upper() for c in codes]
        self.count = int(count) if count else len(self.codes)

    def score_selection(self, selection) -> float:
        satisfied = set()
        for cand in selection:
            satisfied.update(
                c for c in cand.course.core_codes if c.upper() in self.codes
            )
        missing = max(0, self.count - len(satisfied))
        return missing / self.count if self.count else 0.0


_EXAM_RE = re.compile(r"(\d{2}/\d{2}/\d{4}) - (\d{4}) - (\d{4}) ([AP]M)")


def parse_final_exam(text: str) -> tuple[str, int, int] | None:
    """'12/16/2026 - 0400 - 0700 PM' -> ('12/16/2026', 960, 1140), else None.

    The single meridiem applies to the end time; the start borrows it unless
    the raw digits run backwards (1100 - 0200 PM means 11 AM to 2 PM).
    """
    m = _EXAM_RE.match(text.strip())
    if not m:
        return None
    date, raw_start, raw_end, meridiem = m.groups()

    def to_minutes(raw: str, pm: bool) -> int:
        hour, minute = int(raw[:2]) % 12, int(raw[2:])
        return (hour + (12 if pm else 0)) * 60 + minute

    end_pm = meridiem == "PM"
    start_pm = end_pm if int(raw_start) <= int(raw_end) else not end_pm
    start, end = to_minutes(raw_start, start_pm), to_minutes(raw_end, end_pm)
    if start >= end:
        return None
    return date, start, end


class NoFinalExamConflicts(SelectionConstraint):
    type_name = "no_final_exam_conflicts"

    def score_selection(self, selection) -> float:
        exams = [
            parsed
            for cand in selection
            if cand.section.final_exam
            and (parsed := parse_final_exam(cand.section.final_exam))
        ]
        if len(exams) < 2:
            return 0.0
        pairs = conflicts = 0
        for i, (date_a, start_a, end_a) in enumerate(exams):
            for date_b, start_b, end_b in exams[i + 1:]:
                pairs += 1
                if date_a == date_b and start_a < end_b and start_b < end_a:
                    conflicts += 1
        return conflicts / pairs


# ---------------------------------------------------------------------------
# registry + factory

CONSTRAINT_TYPES: dict[str, type[BaseConstraint]] = {
    cls.type_name: cls
    for cls in (
        NoClassesBefore, NoClassesAfter, NoClassesOnDays, AvoidEarlyMornings,
        PreferInstructor, AvoidInstructor, OpenSectionsOnly, PreferAsync,
        PreferCampus, AvoidCampus, PreferHonors, AvoidHonors,
        MaxDaysWithClasses, FreeDayOn, MaxGapPerDay, CompactDays, LunchBreak,
        GetOutBy, MaxClassesPerDay, TravelComfort,
        CreditRange, CoreCoverage, NoFinalExamConflicts,
    )
}


@dataclass
class CatalogContext:
    """What the factory resolves LLM output against."""

    courses: list[Course] = field(default_factory=list)
    valid_core_codes: set[str] = field(default_factory=set)
    assumed_credits: float = 3.0

    @property
    def instructor_names(self) -> set[str]:
        return {
            name
            for course in self.courses
            for section in course.sections
            for name in section.instructors
        }


_DAY_LOOKUP = {name.casefold(): i for i, name in enumerate(DAY_NAMES)}
_DAY_LOOKUP.update({name[:3].casefold(): i for i, name in enumerate(DAY_NAMES)})

_CAMPUS_LOOKUP = {name.casefold(): code for code, name in CAMPUS_LOCATIONS.items()}
_CAMPUS_LOOKUP.update({
    "cac": "1", "college ave": "1", "busch": "2", "livingston": "3", "livi": "3",
    "cook": "4", "douglass": "4", "cook/douglass": "4", "downtown": "5",
})


def _parse_hhmm(value) -> int | None:
    """'15:30' -> 930. Tolerates bare hour ints the LLM might slip into."""
    if isinstance(value, (int, float)):
        v = int(value)
        return v * 60 if 0 <= v <= 24 else None
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(value).strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 24 or minute > 59:
        return None
    return hour * 60 + minute


def _parse_days(value) -> list[int] | None:
    if not value:
        return None
    days = []
    for item in value:
        day = _DAY_LOOKUP.get(str(item).strip().casefold())
        if day is not None:
            days.append(day)
    return days or None


def _parse_campuses(value) -> list[str]:
    codes = []
    for item in value or []:
        text = str(item).strip()
        if text in CAMPUS_LOCATIONS:
            codes.append(text)
            continue
        code = _CAMPUS_LOOKUP.get(text.casefold())
        if code:
            codes.append(code)
    return codes


def _resolve_course(value: str, ctx: CatalogContext) -> str | None:
    """Exact course_string match first, else fuzzy title match."""
    text = str(value).strip()
    by_string = {c.course_string: c for c in ctx.courses}
    if text in by_string:
        return text
    titles: dict[str, str] = {}
    for c in ctx.courses:
        for t in (c.title, c.expanded_title):
            if t:
                titles[t.casefold()] = c.course_string
    match = difflib.get_close_matches(text.casefold(), list(titles), n=1, cutoff=0.6)
    return titles[match[0]] if match else None


def _resolve_instructors(names, ctx: CatalogContext) -> list[str]:
    known = {_surname(n): n for n in ctx.instructor_names}
    resolved = []
    for name in names or []:
        hit = next((known[t] for t in _name_tokens(name) if t in known), None)
        if hit:
            resolved.append(hit)
    return resolved


def build_constraints(
    ai_output: list[dict], ctx: CatalogContext
) -> tuple[list[BaseConstraint], list[str]]:
    """LLM JSON -> constraint objects, with repairs recorded as warnings."""
    constraints: list[BaseConstraint] = []
    warnings: list[str] = []
    seen: set[tuple] = set()

    for raw in ai_output or []:
        if not isinstance(raw, dict):
            warnings.append(f"skipped non-object constraint entry: {raw!r}")
            continue
        type_name = raw.get("type", "")
        cls = CONSTRAINT_TYPES.get(type_name)
        if cls is None:
            warnings.append(f"unknown constraint type '{type_name}' — skipped")
            continue

        hard = bool(raw.get("hard", False))
        weight = raw.get("weight", 0.5)
        try:
            weight = max(0.0, min(1.0, float(weight)))
        except (TypeError, ValueError):
            weight = 0.5

        built = _build_one(cls, raw, ctx, hard, weight, warnings)
        if built is None:
            continue

        key = (type_name, tuple(sorted(str(v) for v in raw.items())))
        if key in seen:
            continue
        seen.add(key)
        constraints.append(built)

    return constraints, warnings


def _build_one(cls, raw, ctx, hard, weight, warnings):
    kw = {"hard": hard, "weight": weight}
    name = cls.type_name

    if cls in (NoClassesBefore, NoClassesAfter, AvoidEarlyMornings, GetOutBy):
        time = _parse_hhmm(raw.get("time"))
        if time is None and cls is not AvoidEarlyMornings:
            warnings.append(f"{name}: unparseable time {raw.get('time')!r} — skipped")
            return None
        if time is not None:
            kw["time"] = time
        kw["days"] = _parse_days(raw.get("days"))
        return cls(**kw)

    if cls in (NoClassesOnDays, FreeDayOn):
        days = _parse_days(raw.get("days"))
        if not days:
            warnings.append(f"{name}: no recognizable days in {raw.get('days')!r} — skipped")
            return None
        return cls(days=days, **kw)

    if cls in (PreferInstructor, AvoidInstructor):
        names = _resolve_instructors(raw.get("names") or [raw.get("name")], ctx)
        if not names:
            warnings.append(
                f"{name}: couldn't match instructor {raw.get('names') or raw.get('name')!r} — skipped"
            )
            return None
        course = None
        if raw.get("course"):
            course = _resolve_course(raw["course"], ctx)
            if course is None:
                warnings.append(f"{name}: couldn't match course {raw.get('course')!r}")
        if cls is PreferInstructor:
            if course is None:
                warnings.append(f"{name}: needs a course — skipped")
                return None
            return cls(course_string=course, names=names, **kw)
        return cls(names=names, course_string=course, **kw)

    if cls is OpenSectionsOnly:
        return cls(hard=hard, weight=weight)

    if cls is PreferAsync:
        return cls(maximize=bool(raw.get("maximize", True)), **kw)

    if cls in (PreferCampus, AvoidCampus):
        codes = _parse_campuses(raw.get("campuses") or raw.get("campus_codes"))
        if not codes:
            warnings.append(f"{name}: no recognizable campuses — skipped")
            return None
        return cls(campus_codes=codes, **kw)

    if cls in (PreferHonors, AvoidHonors, NoFinalExamConflicts):
        return cls(**kw)

    if cls is MaxDaysWithClasses:
        return cls(max_days=int(raw.get("max_days", 5)), **kw)

    if cls is MaxGapPerDay:
        gap = raw.get("max_gap_minutes", raw.get("max_gap", 120))
        return cls(max_gap=int(gap), **kw)

    if cls is CompactDays:
        return cls(tight=bool(raw.get("tight", True)), **kw)

    if cls is LunchBreak:
        lo = _parse_hhmm(raw.get("window_start")) or 11 * 60
        hi = _parse_hhmm(raw.get("window_end")) or 14 * 60
        return cls(window=(lo, hi), min_free=int(raw.get("min_free", 30)), **kw)

    if cls is MaxClassesPerDay:
        return cls(max_count=int(raw.get("max_count", 3)), **kw)

    if cls is TravelComfort:
        return cls(slack=int(raw.get("slack", 10)), **kw)

    if cls is CreditRange:
        return cls(
            min_credits=raw.get("min_credits"),
            max_credits=raw.get("max_credits"),
            assumed_credits=ctx.assumed_credits,
            **kw,
        )

    if cls is CoreCoverage:
        codes = [
            str(c).upper() for c in raw.get("codes") or []
            if not ctx.valid_core_codes or str(c).upper() in ctx.valid_core_codes
        ]
        if not codes:
            warnings.append(f"{name}: no valid core codes in {raw.get('codes')!r} — skipped")
            return None
        return cls(codes=codes, count=raw.get("count"), **kw)

    warnings.append(f"{name}: no builder — skipped")
    return None


def default_constraints(open_only: bool = True) -> list[BaseConstraint]:
    """Always-on defaults the user never has to ask for. The hard 35-minute
    cross-campus rule is enforced structurally by the generator and needs no
    constraint object."""
    defaults: list[BaseConstraint] = [TravelComfort(slack=10, weight=0.5)]
    if open_only:
        defaults.append(OpenSectionsOnly(hard=True))
    return defaults
