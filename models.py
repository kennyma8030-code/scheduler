from pydantic import BaseModel
from typing import List

class FixedEvent(BaseModel):
    name: str
    start: int
    finish: int
    in_dorm: bool

class FlexibleEvent(BaseModel):
    name: str 
    duration: int
    in_dorm: bool

class Schedule(BaseModel):
    roommate_name: str
    fixed_events: List[FixedEvent]
    flexible_events: List[FlexibleEvent]

class Scheduler(BaseModel):
    roommate_a: Schedule 
    roommate_b: Schedule

