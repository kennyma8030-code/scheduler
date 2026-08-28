"""Time units shared across the scheduler.

Everything on the wire and inside the course generator counts in *minutes
since midnight*. The one exception is conflict detection, which quantizes
meetings into fixed-width buckets of ``SLOT_MINUTES`` so a day fits in a single
integer bitmask; 5 minutes is fine enough for a Rutgers meeting time
(15:50-17:10 is typical) without inflating the mask.
"""

from __future__ import annotations

SLOT_MINUTES = 5
MINUTES_PER_DAY = 24 * 60

# Shortest hole in a day that counts as an actual break rather than a walk
# between buildings: the 10-minute passing period between two back-to-back
# classes should not register as a gap.
BREAK_MIN_MINUTES = 30


def fmt_minutes(minutes: int) -> str:
    # End-of-day is 1440, not 0 — showing "00:00" for it reads as midnight-start.
    minutes = int(minutes)
    if minutes != MINUTES_PER_DAY:
        minutes %= MINUTES_PER_DAY
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
