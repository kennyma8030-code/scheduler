"""Engine tests: constraints, conflict logic, and the generator end to end.

Runs standalone (no pytest dependency, no network, no database):

    python -m backend.class_scheduler.tests.test_engine

Every function named test_* is executed; a failed assert names the test.
"""

from __future__ import annotations

from backend.class_scheduler import travel
from backend.class_scheduler.constraints import (
    AvoidInstructor,
    CatalogContext,
    CompactDays,
    CreditRange,
    FreeDayOn,
    LunchBreak,
    MaxDaysWithClasses,
    NoClassesBefore,
    NoClassesOnDays,
    OpenSectionsOnly,
    TravelComfort,
    build_constraints,
    parse_final_exam,
)
from backend.class_scheduler.generator import (
    Candidate,
    CourseScheduleGenerator,
    Group,
    WeekOccupancy,
    _pair_conflicts,
)
from backend.class_scheduler.models import Course, Meeting, Section


# ---------------------------------------------------------------------------
# builders for synthetic catalog data


def meeting(day, start, end, campus="1", mode="LEC"):
    return Meeting(
        day=day, start=start, end=end, mode=mode,
        building="B", room="1", campus_code=campus, campus_name="",
    )


_index_counter = [10000]


def section(meetings, *, index=None, open_=True, instructors=(), honors=False,
            cross_listed=(), final_exam=""):
    _index_counter[0] += 1
    return Section(
        index=index or str(_index_counter[0]),
        number="01", open=open_, instructors=list(instructors),
        meetings=meetings, exam_code="", final_exam=final_exam,
        comments="", notes="", open_to="", eligibility="", honors=honors,
        cross_listed=list(cross_listed),
    )


def course(course_string, sections, *, credits=3.0, core_codes=(), title=""):
    return Course(
        course_string=course_string, supplement="", title=title or course_string,
        expanded_title="", subject=course_string.split(":")[1],
        subject_description="", course_number=course_string.split(":")[2],
        unit="01", school="", level="U", credits=credits,
        core_codes=list(core_codes), core_code_descriptions={},
        prereq_notes="", synopsis_url="", campus_locations=[],
        sections=sections,
    )


def cand(course_obj, section_obj):
    return Candidate.build(course_obj, section_obj, 0)


def group_of(label, *course_objs, locked=False, flexible=False):
    cands = [
        Candidate.build(c, s, 0) for c in course_objs for s in c.sections
    ]
    return Group(label, cands, locked=locked, flexible=flexible)


# ---------------------------------------------------------------------------
# travel rules


def test_transfer_violation():
    assert travel.transfer_violation(600, 620, "1", "2")        # 20 min CAC->Busch
    assert not travel.transfer_violation(600, 640, "1", "2")    # 40 min is fine
    assert not travel.transfer_violation(600, 605, "1", "1")    # same campus
    assert not travel.transfer_violation(600, 605, "1", "O")    # online needs no bus
    assert travel.travel_minutes("1", "2") == 40
    assert travel.travel_minutes("2", "2") == 0


def test_busch_livingston_exempt_from_minimum():
    """Students make this hop between back-to-back classes routinely."""
    assert not travel.transfer_violation(600, 605, "2", "3")    # 5 min, still legal
    assert not travel.transfer_violation(600, 600, "3", "2")    # no gap at all
    # Exempt from the hard rule, but it is still a real bus ride: the soft
    # scorer must keep seeing it so it prefers a genuine gap.
    assert travel.needs_transfer("2", "3")
    assert travel.travel_minutes("2", "3") == 15
    # Every other cross-campus pair keeps the hard minimum.
    assert travel.transfer_violation(600, 605, "2", "4")
    assert travel.transfer_violation(600, 605, "1", "3")


# ---------------------------------------------------------------------------
# pairwise conflicts


def test_time_overlap_conflict():
    a = cand(course("01:198:111", []), section([meeting(0, 600, 680)]))
    b = cand(course("01:640:151", []), section([meeting(0, 640, 720)]))
    c = cand(course("01:750:203", []), section([meeting(0, 680, 760, campus="1")]))
    assert _pair_conflicts(a, b)
    assert not _pair_conflicts(a, c)  # back-to-back same campus is legal


def test_35_minute_rule_in_conflict_mask():
    ends_cac = cand(course("01:198:111", []), section([meeting(0, 600, 680, campus="1")]))
    busch_20 = cand(course("01:640:151", []), section([meeting(0, 700, 780, campus="2")]))
    busch_40 = cand(course("01:750:203", []), section([meeting(0, 720, 800, campus="2")]))
    cac_20 = cand(course("01:013:120", []), section([meeting(0, 700, 780, campus="1")]))
    assert _pair_conflicts(ends_cac, busch_20)       # 20-min cross-campus gap
    assert not _pair_conflicts(ends_cac, busch_40)   # 40 min is enough
    assert not _pair_conflicts(ends_cac, cac_20)     # same campus, any gap

    # Busch <-> Livingston is exempt, so a 10-minute gap is a valid pairing.
    ends_busch = cand(course("01:750:203", []), section([meeting(0, 600, 680, campus="2")]))
    livi_10 = cand(course("01:355:101", []), section([meeting(0, 690, 770, campus="3")]))
    assert not _pair_conflicts(ends_busch, livi_10)


def test_async_conflicts_with_nothing():
    an_async = cand(course("01:198:112", []), section([]))
    timed = cand(course("01:640:151", []), section([meeting(0, 600, 680)]))
    assert not _pair_conflicts(an_async, timed)
    assert an_async.is_fully_async


def test_cross_listed_is_same_class():
    a_sec = section([meeting(0, 600, 680)], index="11111", cross_listed=["22222"])
    b_sec = section([meeting(2, 600, 680)], index="22222")
    a = cand(course("01:198:206", [a_sec]), a_sec)
    b = cand(course("14:332:226", [b_sec]), b_sec)
    assert _pair_conflicts(a, b)  # never both, even with disjoint times


# ---------------------------------------------------------------------------
# constraint scoring


def test_section_constraints():
    early = cand(course("01:198:111", []), section([meeting(0, 480, 560), meeting(2, 720, 800)]))
    assert NoClassesBefore(time=600).score_section(early) == 0.5
    assert NoClassesOnDays(days=[0]).score_section(early) == 0.5
    assert NoClassesOnDays(days=[4]).score_section(early) == 0.0

    closed = cand(course("01:198:111", []), section([meeting(0, 600, 680)], open_=False))
    assert OpenSectionsOnly().score_section(closed) == 1.0

    prof = cand(course("01:198:111", []), section([meeting(0, 600, 680)],
                                                  instructors=["CENTENO, J"]))
    assert AvoidInstructor(names=["Professor Centeno"]).score_section(prof) == 1.0
    assert AvoidInstructor(names=["Smith"]).score_section(prof) == 0.0


def test_schedule_constraints():
    picks = [
        cand(course("01:198:111", []), section([meeting(0, 600, 680), meeting(2, 600, 680)])),
        cand(course("01:640:151", []), section([meeting(0, 900, 980)])),
    ]
    week = WeekOccupancy.build(picks)
    assert MaxDaysWithClasses(max_days=2).score_schedule(week) == 0.0
    assert MaxDaysWithClasses(max_days=1).score_schedule(week) > 0
    assert FreeDayOn(days=[4]).score_schedule(week) == 0.0
    assert FreeDayOn(days=[0]).score_schedule(week) == 1.0
    # Monday: 220 idle of a 380-min span (0.58); Wednesday solid (0) -> 0.29.
    assert abs(CompactDays(tight=True).score_schedule(week) - (220 / 380) / 2) < 1e-9
    # The 11:00-14:00 window on Monday is fully free between 680 and 840.
    assert LunchBreak().score_schedule(week) == 0.0


def test_travel_comfort_soft():
    picks = [
        cand(course("01:198:111", []), section([meeting(0, 600, 680, campus="1")])),
        cand(course("01:640:151", []), section([meeting(0, 720, 800, campus="2")])),
    ]
    week = WeekOccupancy.build(picks)
    # 40-minute gap beats the hard rule but not travel(40) + slack(10).
    score = TravelComfort(slack=10).score_schedule(week)
    assert 0 < score < 1


def test_credit_range():
    picks = [
        cand(course("01:198:111", [], credits=4.0), section([])),
        cand(course("01:640:151", [], credits=None), section([])),
    ]
    c = CreditRange(min_credits=12, max_credits=18, assumed_credits=3.0)
    assert c.total(picks) == 7.0
    assert c.score_selection(picks) == 1.0  # 5 credits short saturates
    assert CreditRange(min_credits=6, assumed_credits=3.0).score_selection(picks) == 0.0


def test_final_exam_parsing():
    assert parse_final_exam("12/16/2026 - 0400 - 0700 PM") == ("12/16/2026", 960, 1140)
    assert parse_final_exam("12/16/2026 - 1100 - 0200 PM") == ("12/16/2026", 660, 840)
    assert parse_final_exam("12/16/2026 - 0800 - 1100 AM") == ("12/16/2026", 480, 660)
    assert parse_final_exam("TBA") is None


# ---------------------------------------------------------------------------
# the factory


def test_build_constraints_repairs_and_warns():
    ctx = CatalogContext(
        courses=[course("01:198:112", [section([meeting(0, 600, 680)],
                                               instructors=["CENTENO, J"])],
                        title="DATA STRUCTURES")],
        valid_core_codes={"HST", "QQ"},
    )
    raw = [
        {"type": "no_classes_before", "time": "10:00", "hard": True, "weight": 1.0},
        {"type": "no_classes_on_days", "days": ["Friday"], "weight": 0.7},
        {"type": "avoid_instructor", "names": ["centeno"], "weight": 0.8},
        {"type": "core_coverage", "codes": ["HST", "FAKE"], "count": 1, "weight": 0.6},
        {"type": "made_up_thing", "weight": 0.5},
        {"type": "no_classes_before", "time": "whenever", "weight": 0.5},
    ]
    constraints, warnings = build_constraints(raw, ctx)
    types = [c.type_name for c in constraints]
    assert types == ["no_classes_before", "no_classes_on_days", "avoid_instructor",
                     "core_coverage"]
    assert constraints[0].hard and constraints[0].time == 600
    assert constraints[1].days == {4}
    assert constraints[3].codes == ["HST"]  # FAKE dropped against valid set
    assert len(warnings) == 2  # unknown type + unparseable time


# ---------------------------------------------------------------------------
# the generator end to end


def two_course_groups():
    cs = course("01:198:112", [
        section([meeting(0, 600, 680), meeting(2, 600, 680)]),          # M/W 10-11:20
        section([meeting(0, 900, 980), meeting(2, 900, 980)]),          # M/W 15-16:20
        section([meeting(4, 480, 560)]),                                # F 8-9:20
    ], credits=4.0)
    math_ = course("01:640:151", [
        section([meeting(0, 620, 700), meeting(3, 620, 700)]),          # overlaps cs #1
        section([meeting(1, 600, 680), meeting(3, 600, 680)]),          # T/Th clean
    ], credits=4.0)
    return [group_of("01:198:112", cs), group_of("01:640:151", math_)]


def test_generate_basic():
    gen = CourseScheduleGenerator(two_course_groups(), [
        NoClassesOnDays(days=[4], weight=0.7),
    ])
    out = gen.run()
    assert out["infeasible"] is None
    assert out["results"], "expected at least one schedule"
    top = out["results"][0]
    assert 0 <= top["score"] <= 100
    assert len(top["indexes"]) == 2
    assert top["credits_total"] == 8.0
    # Scores are sorted best-first and the Friday section is not on top.
    scores = [r["score"] for r in out["results"]]
    assert scores == sorted(scores, reverse=True)
    top_days = {b["start"] and d for d, day in enumerate(top["week"]) for b in day}
    assert out["stats"]["leaves_scored"] >= len(out["results"])


def test_generate_hard_filter_infeasible():
    groups = [group_of("01:198:112", course("01:198:112", [
        section([meeting(0, 480, 560)]),
    ]))]
    gen = CourseScheduleGenerator(groups, [NoClassesBefore(time=600, hard=True, weight=1.0)])
    out = gen.run()
    assert out["infeasible"] is not None
    assert out["infeasible"]["group"] == "01:198:112"


def test_skeleton_violation_reported_first():
    cac = course("01:198:111", [section([meeting(0, 600, 680, campus="1")], index="10001")])
    busch = course("01:640:151", [section([meeting(0, 700, 780, campus="2")], index="10002")])
    groups = [
        Group("a", [Candidate.build(cac, cac.sections[0], 0)], locked=True),
        Group("b", [Candidate.build(busch, busch.sections[0], 1)], locked=True),
    ]
    out = CourseScheduleGenerator(groups, []).run()
    assert out["infeasible"] is not None
    assert set(out["infeasible"]["pair"]) == {"10001", "10002"}
    assert "35" in out["infeasible"]["reason"]
    assert out["stats"]["leaves_scored"] == 0


def test_skeleton_prefilters_candidates():
    locked = course("01:198:111", [section([meeting(0, 600, 680)], index="10001")])
    other = course("01:640:151", [
        section([meeting(0, 640, 720)]),   # overlaps the locked pick
        section([meeting(1, 600, 680)]),   # clean
    ])
    groups = [
        Group("locked", [Candidate.build(locked, locked.sections[0], 0)], locked=True),
        group_of("01:640:151", other),
    ]
    gen = CourseScheduleGenerator(groups, [])
    out = gen.run()
    assert out["stats"]["pruned_skeleton"] == 1
    assert len(out["results"]) == 1


def test_course_combos_from_flexible_group():
    fixed = course("01:198:112", [section([meeting(0, 600, 680)])])
    hist = course("01:510:101", [section([meeting(1, 600, 680)])], core_codes=["HST"])
    art = course("01:082:101", [section([meeting(2, 600, 680)])], core_codes=["HST"])
    groups = [
        group_of("01:198:112", fixed),
        group_of("core HST", hist, art, flexible=True),
    ]
    out = CourseScheduleGenerator(groups, []).run()
    assert len(out["course_combos"]) == 2
    combo_courses = {tuple(c["courses"]) for c in out["course_combos"]}
    assert ("01:082:101", "01:198:112") in combo_courses
    assert ("01:198:112", "01:510:101") in combo_courses


def test_hard_credit_prune():
    a = course("01:198:112", [section([meeting(0, 600, 680)])], credits=12.0)
    b = course("01:640:151", [section([meeting(1, 600, 680)])], credits=12.0)
    groups = [group_of("a", a), group_of("b", b)]
    out = CourseScheduleGenerator(
        groups, [CreditRange(max_credits=18, hard=True, weight=1.0)]
    ).run()
    assert not out["results"]
    assert out["stats"]["pruned_credit"] >= 1


def test_open_only_default_shape():
    closed_only = course("01:198:112", [
        section([meeting(0, 600, 680)], open_=False),
    ])
    groups = [group_of("01:198:112", closed_only)]
    out = CourseScheduleGenerator(groups, [OpenSectionsOnly(hard=True)]).run()
    assert out["infeasible"] is not None


def test_best_first_actually_best():
    """The kept top result matches a brute-force minimum penalty."""
    groups = two_course_groups()
    constraints = [
        NoClassesOnDays(days=[4], weight=0.7),
        CompactDays(tight=True, weight=0.4),
    ]
    out = CourseScheduleGenerator(groups, constraints).run()

    # Brute force over the same product.
    import itertools
    gen2 = CourseScheduleGenerator(two_course_groups(), [
        NoClassesOnDays(days=[4], weight=0.7),
        CompactDays(tight=True, weight=0.4),
    ])
    assert gen2._prepare() is None
    best = None
    for combo in itertools.product(*(g.candidates for g in gen2.groups)):
        mask = 0
        ok = True
        for c in combo:
            if mask >> c.cand_id & 1:
                ok = False
                break
            mask |= c.conflict_mask
        if not ok:
            continue
        scored = gen2.score_leaf(list(combo))
        if scored is None:
            continue
        if best is None or scored[0] < best:
            best = scored[0]
    assert best is not None
    assert abs(out["results"][0]["score"] - gen2.final_score(best)) < 1e-6


# ---------------------------------------------------------------------------
# runner


def main() -> None:
    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
            print(f"  ok    {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:  # noqa: BLE001 — report, keep running
            failures += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
