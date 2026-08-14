"""Normalized view of the SOC payload.

The raw API is verbose and inconsistent (times appear three different ways,
days are single letters, async sections carry empty meeting records). These
models flatten it into what the scheduler actually needs: day index plus
minutes-since-midnight, which makes overlap checks plain integer math.
"""

from __future__ import annotations

from pydantic import BaseModel

# SOC uses H for Thursday and U for Sunday to keep every day a single letter.
DAY_CODES = {"M": 0, "T": 1, "W": 2, "H": 3, "F": 4, "S": 5, "U": 6}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# campusLocation codes seen in meetingTimes.
CAMPUS_LOCATIONS = {
    "1": "College Avenue",
    "2": "Busch",
    "3": "Livingston",
    "4": "Douglass/Cook",
    "5": "Downtown New Brunswick",
    "O": "Online",
    "Z": "Off Campus",
    "S": "Study Abroad",
}


def _to_minutes(military: str) -> int | None:
    """'1550' -> 950. Returns None for the empty strings async meetings carry."""
    if not military or not military.strip().isdigit() or len(military.strip()) != 4:
        return None
    value = military.strip()
    return int(value[:2]) * 60 + int(value[2:])


class Meeting(BaseModel):
    """One weekly meeting block of a section."""

    day: int | None  # 0=Monday .. 6=Sunday; None when asynchronous
    start: int | None  # minutes since midnight
    end: int | None
    mode: str  # "LEC", "RECIT", "LAB", "ONLINE INSTRUCTION(INTERNET)", ...
    building: str
    room: str
    campus_code: str
    campus_name: str

    @property
    def is_async(self) -> bool:
        return self.day is None or self.start is None

    @property
    def duration(self) -> int:
        if self.start is None or self.end is None:
            return 0
        return self.end - self.start

    def overlaps(self, other: "Meeting") -> bool:
        """True when both meet on the same day at overlapping times.

        Async meetings never conflict — they have no fixed slot to collide in.
        """
        if self.is_async or other.is_async:
            return False
        if self.day != other.day:
            return False
        return self.start < other.end and other.start < self.end  # type: ignore[operator]

    @classmethod
    def from_raw(cls, raw: dict) -> "Meeting":
        return cls(
            day=DAY_CODES.get(raw.get("meetingDay") or ""),
            start=_to_minutes(raw.get("startTimeMilitary") or ""),
            end=_to_minutes(raw.get("endTimeMilitary") or ""),
            mode=raw.get("meetingModeDesc") or "",
            building=raw.get("buildingCode") or "",
            room=raw.get("roomNumber") or "",
            campus_code=raw.get("campusLocation") or "",
            campus_name=raw.get("campusName") or "",
        )


class Section(BaseModel):
    """A registerable section. ``index`` is the 5-digit code used at WebReg."""

    index: str
    number: str  # section number within the course, e.g. "01"
    open: bool
    instructors: list[str]
    meetings: list[Meeting]
    exam_code: str
    final_exam: str  # "12/16/2026 - 0400 - 0700 PM", empty when none scheduled
    comments: str
    notes: str
    open_to: str  # major/school restriction text, empty when unrestricted
    eligibility: str  # e.g. "1ST YEAR ONLY", empty when unrestricted
    honors: bool
    # Registration indexes of cross-listed twins; treat them as the same class.
    cross_listed: list[str]

    @property
    def is_fully_async(self) -> bool:
        return all(m.is_async for m in self.meetings)

    @property
    def campuses(self) -> set[str]:
        return {m.campus_name for m in self.meetings if m.campus_name}

    def conflicts_with(self, other: "Section") -> bool:
        if other.index in self.cross_listed or self.index in other.cross_listed:
            return False
        return any(a.overlaps(b) for a in self.meetings for b in other.meetings)

    @classmethod
    def from_raw(cls, raw: dict) -> "Section":
        return cls(
            index=raw.get("index") or "",
            number=raw.get("number") or "",
            open=bool(raw.get("openStatus")),
            instructors=[i.get("name", "") for i in raw.get("instructors") or []],
            meetings=[Meeting.from_raw(m) for m in raw.get("meetingTimes") or []],
            exam_code=raw.get("examCode") or "",
            final_exam=raw.get("finalExam") or "",
            comments=raw.get("commentsText") or "",
            notes=raw.get("sectionNotes") or "",
            open_to=raw.get("openToText") or "",
            eligibility=raw.get("sectionEligibility") or "",
            honors=bool(raw.get("honorPrograms")),
            cross_listed=[
                x.get("registrationIndex", "")
                for x in raw.get("crossListedSections") or []
            ],
        )


class Course(BaseModel):
    """A course offering. ``course_string`` is the canonical 01:198:112 form."""

    course_string: str
    # Distinguishes co-numbered offerings: "" is the main course, "LB" a
    # separately-registered lab component. Part of the course's natural key.
    supplement: str
    title: str
    expanded_title: str
    subject: str  # "198"
    subject_description: str  # "Computer Science"
    course_number: str  # "112"
    unit: str  # offering unit / school code, "01"
    school: str
    level: str  # "U" undergraduate, "G" graduate
    credits: float | None
    core_codes: list[str]  # SAS core curriculum codes, e.g. ["HST", "WCd"]
    core_code_descriptions: dict[str, str]
    prereq_notes: str
    synopsis_url: str
    campus_locations: list[str]
    sections: list[Section]

    @property
    def open_sections(self) -> list[Section]:
        return [s for s in self.sections if s.open]

    @classmethod
    def from_raw(cls, raw: dict) -> "Course":
        cores = raw.get("coreCodes") or []
        return cls(
            course_string=raw.get("courseString") or "",
            supplement=(raw.get("supplementCode") or "").strip(),
            title=(raw.get("title") or "").strip(),
            expanded_title=(raw.get("expandedTitle") or "").strip(),
            subject=raw.get("subject") or "",
            subject_description=(raw.get("subjectDescription") or "").strip(),
            course_number=raw.get("courseNumber") or "",
            unit=raw.get("offeringUnitCode") or "",
            school=((raw.get("school") or {}).get("description") or "").strip(),
            level=raw.get("level") or "",
            credits=raw.get("credits"),
            core_codes=[c.get("code", "") for c in cores],
            core_code_descriptions={
                c.get("code", ""): c.get("coreCodeDescription", "") for c in cores
            },
            prereq_notes=raw.get("preReqNotes") or "",
            synopsis_url=raw.get("synopsisUrl") or "",
            campus_locations=[
                c.get("description", "") for c in raw.get("campusLocations") or []
            ],
            sections=[Section.from_raw(s) for s in raw.get("sections") or []],
        )


def merge_split_courses(courses: list[Course]) -> list[Course]:
    """Collapse records that describe the same offering.

    The API sometimes emits one course as two records with its sections split
    between them — 9 of 4438 in Fall 2026 NB, e.g. 16:400:603 arrives as
    indexes ['19376','19377'] and ['19378']. Taking either record alone would
    silently hide half the sections, so we union them.

    Records that differ only by ``supplement`` (a lecture and its separately
    registered lab) are *not* merged: they are distinct offerings.
    """
    merged: dict[tuple[str, str], Course] = {}
    for course in courses:
        key = (course.course_string, course.supplement)
        first = merged.get(key)
        if first is None:
            merged[key] = course
            continue
        seen = {s.index for s in first.sections}
        first.sections.extend(s for s in course.sections if s.index not in seen)
    return list(merged.values())


def parse_courses(raw_courses: list[dict], open_indexes: set[str] | None = None) -> list[Course]:
    """Parse the raw dump, optionally overriding stale open/closed flags.

    ``courses.json`` is cached for 15 minutes, so its ``openStatus`` drifts.
    Passing the live index set from ``openSections.json`` corrects it.
    """
    courses = merge_split_courses([Course.from_raw(c) for c in raw_courses])
    if open_indexes is not None:
        for course in courses:
            for section in course.sections:
                section.open = section.index in open_indexes
    return courses
