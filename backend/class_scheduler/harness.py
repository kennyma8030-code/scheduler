"""Live end-to-end harness for the generator, modeled on explore.py.

    python -m backend.class_scheduler.harness [term_key]

Runs three scenarios against the synced database (run sync first):

    1. mostly locked  — course-locked requirements, one flexible core group
    2. infeasible     — a hard constraint that empties a group
    3. stress         — several flexible groups, forcing the big search path

Prints the funnel stats and the top schedules so the pruning behavior and
timing are visible at a glance.
"""

from __future__ import annotations

import sys

from backend.timegrid import fmt_minutes
from backend.class_scheduler import catalog
from backend.class_scheduler.constraints import (
    CompactDays,
    NoClassesBefore,
    NoClassesOnDays,
    default_constraints,
)
from backend.class_scheduler.generator import CourseScheduleGenerator
from backend.class_scheduler.models import DAY_NAMES
from backend.class_scheduler.schema import make_session_factory


def show(out: dict, title: str) -> None:
    print(f"\n=== {title} ===")
    stats = out["stats"]
    print(
        f"raw {stats.get('raw_product', 0):,} | leaves {stats.get('leaves_scored', 0):,} | "
        f"pruned conflict {stats.get('pruned_conflict', 0):,} / bound {stats.get('pruned_bound', 0):,} / "
        f"hard {stats.get('pruned_hard', 0) + stats.get('pruned_hard_filter', 0):,} / "
        f"skeleton {stats.get('pruned_skeleton', 0):,} | "
        f"workers {stats.get('workers', 1)} | truncated {stats.get('truncated', False)} | "
        f"{stats.get('elapsed_ms', 0)} ms"
    )
    for warning in out["warnings"]:
        print(f"  ! {warning}")
    if out["infeasible"]:
        print(f"  INFEASIBLE: {out['infeasible']}")
        return
    for combo in out["course_combos"]:
        best = combo["results"][0]
        print(f"\n  courses: {', '.join(combo['courses'])} "
              f"({len(combo['results'])} variants, best {best['score']})")
        for day, blocks in enumerate(best["week"]):
            if not blocks:
                continue
            line = "  ".join(
                f"{b['course_string']}@{fmt_minutes(b['start'])}-{fmt_minutes(b['end'])}"
                f"[{b['campus_code']}]"
                for b in blocks
            )
            print(f"    {DAY_NAMES[day][:3]}  {line}")
        print(f"    indexes: {', '.join(best['indexes'])}  "
              f"credits: {best['credits_total']}")


def main() -> None:
    term_key = sys.argv[1] if len(sys.argv) > 1 else "2026-9-NB"
    session = make_session_factory()()
    open_indexes = catalog.open_indexes_for(term_key)

    def run(requirements, constraints, title, **options):
        groups, infeasible = catalog.build_groups(
            session, term_key, requirements, open_indexes
        )
        if infeasible:
            print(f"\n=== {title} ===\n  INFEASIBLE at build: {infeasible}")
            return
        gen = CourseScheduleGenerator(
            groups, constraints + default_constraints(), **options
        )
        show(gen.run(), title)

    # 1. The common case: known courses + one flexible core group.
    run(
        [
            catalog.Requirement(kind="course", course_string="01:198:111"),
            catalog.Requirement(kind="course", course_string="01:640:151"),
            catalog.Requirement(kind="course", course_string="01:220:102"),
            catalog.Requirement(kind="core", core_code="HST"),
        ],
        [
            NoClassesOnDays(days=[4], weight=0.7),
            NoClassesBefore(time=10 * 60, weight=0.6),
            CompactDays(tight=True, weight=0.4),
        ],
        "mostly locked: 3 courses + core HST filler",
    )

    # 2. A hard constraint that kills a group reports cleanly.
    run(
        [catalog.Requirement(kind="course", course_string="01:198:111")],
        [NoClassesBefore(time=20 * 60, hard=True, weight=1.0)],
        "infeasible: CS111 with nothing before 20:00 (hard)",
    )

    # 3. Stress: several flexible core groups -> big product.
    run(
        [
            catalog.Requirement(kind="core", core_code="HST"),
            catalog.Requirement(kind="core", core_code="AHp"),
            catalog.Requirement(kind="core", core_code="SCL"),
            catalog.Requirement(kind="core", core_code="NS"),
            catalog.Requirement(kind="core", core_code="QQ"),
        ],
        [
            NoClassesOnDays(days=[4], weight=0.7),
            CompactDays(tight=True, weight=0.4),
        ],
        "from scratch: five flexible core groups",
        time_budget_s=30.0,
    )


if __name__ == "__main__":
    main()
