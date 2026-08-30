"""Open/closed polling for the Schedule of Classes.

``openSections.json`` is a *snapshot*, not a change feed: a flat list of the
registration indexes currently open. There is no endpoint that reports what
moved, so detecting change means diffing the fetched set against the last
known state. That is cheap — the payload is ~25 KB gzipped and the diff is a
set difference over ~11k strings, well under a millisecond — and it never
touches course data.

Only *transitions* are stored. Persisting a full snapshot per tick would
write ~12k near-identical rows every run to record a boolean that rarely
changes.

Run as a one-shot, which is what a scheduler like Railway cron expects:

    python -m backend.class_scheduler.poll                # every synced term
    python -m backend.class_scheduler.poll 2026-9-NB      # one term
    python -m backend.class_scheduler.poll --report       # recent activity

The process fetches, writes, disposes the engine, and exits. Exiting matters:
Railway skips subsequent executions while a previous one is still alive, so a
poller that fails to terminate silently stops polling forever.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.class_scheduler import catalog, schema
from backend.class_scheduler.soc import SOCClient, SOCError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def apply_snapshot(
    session: Session, term_key: str, open_now: set[str], at: str | None = None
) -> dict:
    """Diff a fetched open-set against stored state and record what moved.

    Split out from the fetch so the diff logic is testable without network.
    The first call for a term seeds state without logging transitions —
    otherwise every section would register as a change on day one.
    """
    at = at or _now()

    universe = set(
        session.execute(
            select(schema.Section.index)
            .join(schema.Course)
            .where(schema.Course.term_key == term_key)
        ).scalars()
    )
    if not universe:
        return {"term_key": term_key, "error": "term not synced", "changes": 0}

    stored = {
        row.index: row
        for row in session.execute(
            select(schema.SectionStatus).where(
                schema.SectionStatus.term_key == term_key
            )
        ).scalars()
    }
    seeding = not stored

    opened = closed = 0
    for index in universe:
        is_open = index in open_now
        row = stored.get(index)

        if row is None:
            # New to us: a first run, or a section added by a later sync.
            session.add(
                schema.SectionStatus(
                    term_key=term_key, index=index, is_open=is_open, since=at
                )
            )
            continue

        if row.is_open == is_open:
            continue

        row.is_open = is_open
        row.since = at
        session.add(
            schema.SectionStatusChange(
                term_key=term_key, index=index, is_open=is_open, at=at
            )
        )
        if is_open:
            opened += 1
        else:
            closed += 1

    stats = {
        "term_key": term_key,
        "at": at,
        "open_count": len(open_now & universe),
        "opened": opened,
        "closed": closed,
        # Open indexes outside this term's catalog. Expected, and not a
        # staleness signal: openSections.json ignores the campus parameter
        # (NB, NK and CM return byte-identical sets), so every response is
        # university-wide and the surplus is other campuses. Tracked because a
        # sudden change in it is still worth noticing.
        "outside_catalog": len(open_now - universe),
        "seeded": seeding,
        "tracked": len(universe),
    }
    session.add(
        schema.PollRun(
            term_key=term_key,
            at=at,
            open_count=stats["open_count"],
            opened=opened,
            closed=closed,
            unknown=stats["outside_catalog"],
        )
    )
    session.commit()
    return stats


def poll_term(session: Session, term_key: str, client: SOCClient | None = None) -> dict:
    """Fetch one term's open set and record the diff."""
    try:
        open_now = catalog.open_indexes_for(term_key, client)
    except (SOCError, ValueError, OSError) as exc:
        # A failed tick is survivable: the next one re-reads the full snapshot,
        # so nothing needs recovering. Only a lasting outage loses resolution.
        return {"term_key": term_key, "error": str(exc), "changes": 0}
    return apply_snapshot(session, term_key, open_now)


def synced_terms(session: Session) -> list[str]:
    return list(
        session.execute(select(schema.Term.key).order_by(schema.Term.key)).scalars()
    )


def report(session: Session, limit: int = 10) -> None:
    runs = session.execute(
        select(schema.PollRun).order_by(schema.PollRun.id.desc()).limit(limit)
    ).scalars().all()
    print(f"--- last {len(runs)} poll runs")
    for r in runs:
        print(
            f"   {r.at}  {r.term_key:<12} open {r.open_count:>6}"
            f"   +{r.opened} opened  -{r.closed} closed"
            + (f"   ({r.unknown} unknown)" if r.unknown else "")
        )

    changes = session.execute(
        select(schema.SectionStatusChange)
        .order_by(schema.SectionStatusChange.id.desc())
        .limit(limit)
    ).scalars().all()
    print(f"\n--- last {len(changes)} transitions")
    for c in changes:
        print(f"   {c.at}  {c.term_key:<12} idx {c.index}  "
              f"{'OPENED' if c.is_open else 'closed'}")
    if not changes:
        print("   (none recorded yet)")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    engine = schema.make_engine()
    schema.create_all(engine)
    session = schema.make_session_factory(engine)()
    failed = False
    try:
        if "--report" in flags:
            report(session)
            return 0

        terms = args or synced_terms(session)
        if not terms:
            print("no synced terms; run backend.class_scheduler.sync first")
            return 1

        client = SOCClient()
        for term_key in terms:
            stats = poll_term(session, term_key, client)
            if stats.get("error"):
                failed = True
                print(f"{term_key}: FAILED — {stats['error']}")
                continue
            note = "  (seeded initial state)" if stats["seeded"] else ""
            print(
                f"{stats['at']}  {term_key}: {stats['open_count']} open of "
                f"{stats['tracked']}, +{stats['opened']} opened, "
                f"-{stats['closed']} closed{note}"
            )
            if stats["outside_catalog"]:
                print(f"   ({stats['outside_catalog']} open indexes are other "
                      "campuses - openSections ignores the campus filter)")
    finally:
        # Release everything explicitly: a cron process that lingers on an open
        # pool blocks every future run.
        session.close()
        engine.dispose()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
