"""Live smoke test / exploration script for the SOC client.

    python -m backend.class_scheduler.explore [year] [term] [campus]

Hits the real API, parses the dump, and prints a summary plus a few worked
examples (a course lookup, a core-code lookup, a conflict check). Useful for
confirming the API still behaves as documented in API_NOTES.md.
"""

from __future__ import annotations

import sys
from collections import Counter

from backend.class_scheduler.models import DAY_NAMES, parse_courses
from backend.class_scheduler.soc import SOCClient, resolve_term


def fmt_time(minutes: int | None) -> str:
    if minutes is None:
        return "--:--"
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def describe(section) -> str:
    if section.is_fully_async:
        return "asynchronous"
    parts = []
    for m in section.meetings:
        if m.is_async:
            continue
        where = f"{m.building} {m.room}".strip() or m.campus_name
        parts.append(
            f"{DAY_NAMES[m.day][:3]} {fmt_time(m.start)}-{fmt_time(m.end)} "
            f"{m.mode} @ {where}"
        )
    return "; ".join(parts)


def main() -> None:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    term = resolve_term(sys.argv[2]) if len(sys.argv) > 2 else "9"
    campus = sys.argv[3] if len(sys.argv) > 3 else "NB"

    client = SOCClient()
    raw = client.courses(year, term, campus)
    open_indexes = client.open_section_indexes(year, term, campus)
    courses = parse_courses(raw, open_indexes)

    sections = [s for c in courses for s in c.sections]
    meetings = [m for s in sections for m in s.meetings]

    print(f"=== {year} term {term} {campus} ===")
    print(f"courses            {len(courses)}")
    print(f"sections           {len(sections)}")
    print(f"  open             {sum(1 for s in sections if s.open)}")
    print(f"  fully async      {sum(1 for s in sections if s.is_fully_async)}")
    print(f"meetings           {len(meetings)}")
    print(f"  timed            {sum(1 for m in meetings if not m.is_async)}")
    print(f"subjects           {len({c.subject for c in courses})}")
    print(f"undergrad courses  {sum(1 for c in courses if c.level == 'U')}")

    print("\n--- meetings per day (timed only)")
    days = Counter(m.day for m in meetings if not m.is_async)
    for day in range(7):
        if days[day]:
            print(f"   {DAY_NAMES[day]:<10} {days[day]}")

    print("\n--- core codes offered")
    cores: Counter[str] = Counter()
    labels: dict[str, str] = {}
    for c in courses:
        for code in c.core_codes:
            cores[code] += 1
            labels[code] = c.core_code_descriptions.get(code, "")
    for code, count in cores.most_common():
        print(f"   {code:<8} {count:>4} courses   {labels[code]}")

    print("\n--- example: open CS sections meeting no earlier than 10:00 and never on Friday")
    shown = 0
    for c in courses:
        if c.subject != "198" or c.level != "U":
            continue
        for s in c.sections:
            if not s.open or s.is_fully_async:
                continue
            timed = [m for m in s.meetings if not m.is_async]
            if any(m.day == 4 for m in timed):
                continue
            if any(m.start is not None and m.start < 600 for m in timed):
                continue
            print(f"   {c.course_string} {c.title[:34]:<34} idx {s.index}  {describe(s)}")
            shown += 1
            if shown >= 8:
                break
        if shown >= 8:
            break

    print("\n--- example: conflict detection")
    candidates = [
        s for c in courses for s in c.sections if not s.is_fully_async and s.meetings
    ][:400]
    pairs = sum(
        1
        for i, a in enumerate(candidates)
        for b in candidates[i + 1 :]
        if a.conflicts_with(b)
    )
    n = len(candidates)
    print(f"   {pairs} conflicting pairs among the first {n} timed sections "
          f"({pairs * 2 / (n * (n - 1)):.1%} of pairs)")


if __name__ == "__main__":
    main()
