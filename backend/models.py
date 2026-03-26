from pydantic import BaseModel, model_validator
from typing import List, Set
from enum import Enum


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

class FixedEvent(BaseModel):
    name: str
    start: int
    finish: int
    in_dorm: bool = False
    duration: int = 0

    @model_validator(mode="after")
    def compute_duration(self):
        self.duration = abs(self.finish - self.start)
        return self

class FlexibleEvent(BaseModel):
    name: str 
    duration: int
    in_dorm: bool

class WeeklyFixedEvent(BaseModel):
    name: str
    start: int
    finish: int
    in_dorm: bool = False
    duration: int = 0
    days: Set[int]

    @model_validator(mode="after")
    def compute_duration(self):
        self.duration = abs(self.finish - self.start)
        return self

class WeeklyFlexibleEvent(BaseModel):
    name: str
    duration: int
    in_dorm: bool
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

