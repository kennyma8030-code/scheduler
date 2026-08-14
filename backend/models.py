"""Request models for the scheduler.

Units at this boundary are **minutes since midnight** (0-1440). Everything
inside the optimizer works in 5-minute slots; the validators below do the
conversion once, on the way in, so no scheduling code has to think about it.

Each event therefore carries both:
    start / finish / duration_minutes   minutes, as sent and as returned
    start_slot / finish_slot / duration slots, what the algorithm consumes

``duration`` is in slots because every constraint in templates.py uses it as
the denominator for a per-slot violation count.
"""

from pydantic import BaseModel, model_validator
from typing import List, Set
from enum import Enum

from backend.timegrid import (
    MINUTES_PER_DAY,
    SLOTS_PER_DAY,
    minutes_to_slot,
    minutes_to_slots,
)


class EventCategory(str, Enum):
    sleep    = "sleep"
    work     = "work"
    study    = "study"
    exercise = "exercise"
    personal = "personal"
    social   = "social"
    errands  = "errands"
    leisure  = "leisure"
    other    = "other"


class _TimedEvent(BaseModel):
    """Shared slot derivation for events with an explicit start and finish."""

    start: int    # minutes since midnight
    finish: int   # minutes since midnight
    start_slot: int = 0
    finish_slot: int = 0
    duration: int = 0          # slots
    duration_minutes: int = 0

    @model_validator(mode="after")
    def compute_slots(self):
        start, finish = sorted((int(self.start), int(self.finish)))
        # A finish of exactly midnight means "end of day", not slot 0.
        self.start_slot = minutes_to_slot(start)
        self.finish_slot = (
            minutes_to_slot(finish) if finish < MINUTES_PER_DAY else SLOTS_PER_DAY
        )
        self.duration_minutes = finish - start
        self.duration = max(0, self.finish_slot - self.start_slot)
        return self


class FixedEvent(_TimedEvent):
    name: str
    in_dorm: bool = False


class FlexibleEvent(BaseModel):
    """An event the optimizer places. ``duration`` arrives in minutes."""

    name: str
    duration: int  # minutes on the wire, converted to slots below
    in_dorm: bool
    duration_minutes: int = 0

    @model_validator(mode="after")
    def compute_slots(self):
        # Guard against re-running on an already-converted instance.
        if not self.duration_minutes:
            self.duration_minutes = int(self.duration)
            self.duration = minutes_to_slots(self.duration_minutes)
        return self


class WeeklyFixedEvent(FixedEvent):
    days: Set[int]


class WeeklyFlexibleEvent(FlexibleEvent):
    days: Set[int]


class Schedule(BaseModel):
    roommate_name: str
    fixed_events: List[FixedEvent]
    flexible_events: List[FlexibleEvent]

class Schedule_Weekly(BaseModel):
    roommate_name: str
    fixed_events: List[WeeklyFixedEvent]
    flexible_events: List[WeeklyFlexibleEvent]


class Scheduler(BaseModel):
    roommate_a: Schedule
    roommate_b: Schedule

class Scheduler_Weekly(BaseModel):
    roommate_a: Schedule_Weekly
    roommate_b: Schedule_Weekly
