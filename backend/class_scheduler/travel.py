"""Inter-campus travel rules for New Brunswick.

Two same-day meetings on different physical campuses need real transit time
between them. The hard rule is deliberately flat: anything under
``MIN_CAMPUS_TRANSFER_MIN`` minutes is not a schedule, full stop, and the
generator enforces it at every stage (skeleton validation, candidate
pre-filtering, and the pairwise conflict mask).

Busch and Livingston are the exception. They sit a short, frequent bus ride
apart, students make that hop between back-to-back classes routinely, and
Rutgers schedules them as effectively adjacent. That pair is exempt from the
hard minimum — it still costs soft comfort points, just never invalidates a
schedule outright.

The per-pair ``BUS_MINUTES`` estimates below feed only the *soft*
TravelComfort scoring. They are hand-tuned from bus experience, not measured
data — correct them freely; nothing else in the system assumes these exact
numbers.
"""

from __future__ import annotations

# Below this gap, a cross-campus back-to-back pair is invalid outright.
MIN_CAMPUS_TRANSFER_MIN = 35

# Campus codes that are physical New Brunswick locations. Online ("O"),
# off-campus ("Z"), and study abroad ("S") never require a bus.
PHYSICAL_CAMPUSES = frozenset({"1", "2", "3", "4", "5"})

# Rough one-way bus times between campuses, in minutes. Keys are frozensets of
# campusLocation codes: 1 College Ave, 2 Busch, 3 Livingston, 4 Douglass/Cook,
# 5 Downtown New Brunswick.
BUS_MINUTES: dict[frozenset[str], int] = {
    frozenset({"1", "2"}): 40,
    frozenset({"1", "3"}): 35,
    frozenset({"1", "4"}): 25,
    frozenset({"1", "5"}): 10,
    frozenset({"2", "3"}): 15,
    frozenset({"2", "4"}): 45,
    frozenset({"2", "5"}): 45,
    frozenset({"3", "4"}): 40,
    frozenset({"3", "5"}): 40,
    frozenset({"4", "5"}): 20,
}

# Campus pairs close enough that back-to-back classes across them are normal.
# These skip the hard minimum entirely; they still accrue soft comfort cost
# through BUS_MINUTES, so the scorer will prefer a real gap when one exists.
EXEMPT_FROM_MINIMUM: frozenset[frozenset[str]] = frozenset({
    frozenset({"2", "3"}),  # Busch <-> Livingston
})


def needs_transfer(campus_a: str, campus_b: str) -> bool:
    """True when moving between these two campuses takes a bus."""
    return (
        campus_a != campus_b
        and campus_a in PHYSICAL_CAMPUSES
        and campus_b in PHYSICAL_CAMPUSES
    )


def travel_minutes(campus_a: str, campus_b: str) -> int:
    """Estimated one-way transit time, 0 when no transfer is needed."""
    if not needs_transfer(campus_a, campus_b):
        return 0
    return BUS_MINUTES.get(frozenset({campus_a, campus_b}), MIN_CAMPUS_TRANSFER_MIN)


def transfer_violation(end_a: int, start_b: int, campus_a: str, campus_b: str) -> bool:
    """The hard rule: same-day meetings this close on different campuses are
    invalid. Caller guarantees the meetings are on the same day and disjoint
    with ``end_a <= start_b``."""
    if not needs_transfer(campus_a, campus_b):
        return False
    if frozenset({campus_a, campus_b}) in EXEMPT_FROM_MINIMUM:
        return False
    return start_b - end_a < MIN_CAMPUS_TRANSFER_MIN
