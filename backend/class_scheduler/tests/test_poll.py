"""Poller tests: snapshot diffing against an in-memory database.

Runs standalone (no pytest, no network, no real database):

    python -m backend.class_scheduler.tests.test_poll
"""

from __future__ import annotations

from sqlalchemy import select

from backend.class_scheduler import schema
from backend.class_scheduler.poll import apply_snapshot


def fixture(indexes=("10001", "10002", "10003")):
    """A fresh in-memory database holding one term with `indexes` sections."""
    engine = schema.make_engine("sqlite://")
    schema.create_all(engine)
    session = schema.make_session_factory(engine)()

    session.add(schema.Term(
        key="2026-9-NB", year=2026, term="9", campus="NB",
        label="Fall 2026 New Brunswick", synced_at="2026-08-01T00:00:00+00:00",
    ))
    course = schema.Course(
        term_key="2026-9-NB", course_string="01:198:112", supplement_code="",
        subject="198", subject_description="Computer Science", course_number="112",
        unit="01", school="SAS", level="U", credits=4.0, title="DATA STRUCTURES",
    )
    session.add(course)
    session.flush()
    for i in indexes:
        session.add(schema.Section(course_id=course.id, index=i, number=i[-2:]))
    session.commit()
    return session


def changes(session):
    return session.execute(
        select(schema.SectionStatusChange).order_by(schema.SectionStatusChange.id)
    ).scalars().all()


def test_first_run_seeds_without_logging_changes():
    """Day one must not report all 12k sections as transitions."""
    s = fixture()
    stats = apply_snapshot(s, "2026-9-NB", {"10001", "10002"}, at="T0")
    assert stats["seeded"] is True
    assert stats["opened"] == 0 and stats["closed"] == 0
    assert stats["open_count"] == 2
    assert stats["tracked"] == 3
    assert changes(s) == []
    stored = s.execute(select(schema.SectionStatus)).scalars().all()
    assert {r.index: r.is_open for r in stored} == {
        "10001": True, "10002": True, "10003": False
    }


def test_detects_open_and_close():
    s = fixture()
    apply_snapshot(s, "2026-9-NB", {"10001", "10002"}, at="T0")
    stats = apply_snapshot(s, "2026-9-NB", {"10002", "10003"}, at="T1")

    assert stats["opened"] == 1 and stats["closed"] == 1
    logged = {(c.index, c.is_open, c.at) for c in changes(s)}
    assert logged == {("10001", False, "T1"), ("10003", True, "T1")}
    # `since` tracks the flip, not the poll.
    rows = {r.index: r for r in s.execute(select(schema.SectionStatus)).scalars()}
    assert rows["10001"].since == "T1"     # just closed
    assert rows["10002"].since == "T0"     # unchanged, keeps its original stamp


def test_quiet_tick_writes_nothing_but_the_run():
    s = fixture()
    apply_snapshot(s, "2026-9-NB", {"10001"}, at="T0")
    stats = apply_snapshot(s, "2026-9-NB", {"10001"}, at="T1")
    assert (stats["opened"], stats["closed"]) == (0, 0)
    assert changes(s) == []
    # Every tick still leaves a PollRun, so a gap in the change log can be
    # distinguished from the poller being down.
    runs = s.execute(select(schema.PollRun)).scalars().all()
    assert len(runs) == 2


def test_flapping_section_accumulates_history():
    s = fixture()
    apply_snapshot(s, "2026-9-NB", set(), at="T0")
    for i, at in enumerate(["T1", "T2", "T3", "T4"]):
        apply_snapshot(s, "2026-9-NB", {"10001"} if i % 2 == 0 else set(), at=at)
    history = [(c.at, c.is_open) for c in changes(s) if c.index == "10001"]
    assert history == [("T1", True), ("T2", False), ("T3", True), ("T4", False)]


def test_indexes_outside_catalog_counted_not_stored():
    """openSections ignores the campus filter, so responses carry other
    campuses' indexes. They are counted, never written as sections."""
    s = fixture()
    stats = apply_snapshot(s, "2026-9-NB", {"10001", "99999"}, at="T0")
    assert stats["outside_catalog"] == 1
    assert stats["open_count"] == 1          # counts only tracked sections
    stored = s.execute(select(schema.SectionStatus)).scalars().all()
    assert "99999" not in {r.index for r in stored}


def test_section_added_by_later_sync_seeds_quietly():
    s = fixture()
    apply_snapshot(s, "2026-9-NB", {"10001"}, at="T0")
    course_id = s.execute(select(schema.Course.id)).scalar_one()
    s.add(schema.Section(course_id=course_id, index="10004", number="04"))
    s.commit()

    stats = apply_snapshot(s, "2026-9-NB", {"10001", "10004"}, at="T1")
    assert stats["opened"] == 0              # newly tracked, not a transition
    assert stats["tracked"] == 4
    assert changes(s) == []


def test_unsynced_term_reports_error():
    s = fixture()
    stats = apply_snapshot(s, "2027-1-NB", {"10001"}, at="T0")
    assert stats["error"] == "term not synced"


def main() -> None:
    failures = 0
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
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
