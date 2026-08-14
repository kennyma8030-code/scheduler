"""The time grid the scheduler runs on.

Everything downstream of the API boundary counts in *slots*: fixed-width
buckets of ``SLOT_MINUTES`` covering one day. Hour blocks could not represent a
Rutgers class (15:50-17:10 is a typical meeting time), so the grid is 5 minutes.

Three distinct units flow through the system; mixing them up is the easy bug:

    minutes   wire format. Events arrive and leave as minutes since midnight.
    slots     internal grid index, 0..287. All scheduling math uses these.
    hours     what the LLM emits in constraint params, because that is how
              people talk. Converted to slots in constraint_factory.
"""

from __future__ import annotations

SLOT_MINUTES = 5
MINUTES_PER_DAY = 24 * 60
SLOTS_PER_DAY = MINUTES_PER_DAY // SLOT_MINUTES  # 288
SLOTS_PER_HOUR = 60 // SLOT_MINUTES  # 12

# Flexible events are only tried at starts on this boundary. The grid is 12x
# finer than hours and the placement search in ScheduleOptimizer.generate is
# exhaustive, so without a step the search space explodes: three 2-hour events
# go from ~8k placements on the hour grid to ~10.4M on the 5-minute grid, and
# best_schedules takes the *product* of both roommates' lists.
#
# Fixed events keep full 5-minute precision; only the search is coarsened.
# Measured on a 2-flexible-event-each pair with three constraints:
#
#     step     schedules A/B      pairs      time
#     15 min     5572 / 3484    19.4M      98.0s
#     30 min     1410 /  900     1.27M      6.8s   <- default
#     60 min      361 /  240     0.09M      0.5s
#
# 30 minutes is the knob to turn if scheduling gets slow; it costs only the
# ability to start a flexible block at :15 or :45.
PLACEMENT_STEP_MINUTES = 30
PLACEMENT_STEP = PLACEMENT_STEP_MINUTES // SLOT_MINUTES  # 6

# Shortest hole in a day that counts as an actual break rather than a walk
# between buildings. On the hour grid every gap was >= 60 minutes by
# construction; on the 5-minute grid the 10-minute passing period between two
# back-to-back classes would otherwise register as a break.
BREAK_MIN_MINUTES = 30
BREAK_MIN_SLOTS = BREAK_MIN_MINUTES // SLOT_MINUTES  # 6


def minutes_to_slot(minutes: float) -> int:
    """Minutes since midnight -> slot index, rounded down to the slot start."""
    return int(minutes) // SLOT_MINUTES


def slot_to_minutes(slot: int) -> int:
    return slot * SLOT_MINUTES


def hours_to_slots(hours: float) -> int:
    """A *duration* in hours -> a whole number of slots.

    Rounds to nearest so 1.5h is 18 slots rather than 17, and never collapses a
    positive duration to zero (a 2-minute request stays one slot).
    """
    slots = round(float(hours) * SLOTS_PER_HOUR)
    return max(1, int(slots)) if hours else 0


def minutes_to_slots(minutes: float) -> int:
    """A *duration* in minutes -> a whole number of slots."""
    slots = round(float(minutes) / SLOT_MINUTES)
    return max(1, int(slots)) if minutes else 0


def hour_list_to_slots(hours) -> set[int]:
    """Hour-of-day list -> the slot indices those hours cover.

    ``[9, 10]`` becomes every slot from 09:00 to 10:59. Used for constraint
    windows like "study between 9 and 11", which the LLM emits as whole hours.
    """
    slots: set[int] = set()
    for hour in hours or []:
        base = int(hour) * SLOTS_PER_HOUR
        if 0 <= base < SLOTS_PER_DAY:
            slots.update(range(base, min(base + SLOTS_PER_HOUR, SLOTS_PER_DAY)))
    return slots


def fmt_slot(slot: int) -> str:
    """Slot index -> 'HH:MM', for logs and debugging."""
    minutes = slot_to_minutes(slot) % MINUTES_PER_DAY
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def fmt_minutes(minutes: int) -> str:
    # End-of-day is 1440, not 0 — showing "00:00" for it reads as midnight-start.
    minutes = int(minutes)
    if minutes != MINUTES_PER_DAY:
        minutes %= MINUTES_PER_DAY
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
