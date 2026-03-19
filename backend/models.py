from pydantic import BaseModel, model_validator
from typing import List

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

class Schedule(BaseModel):
    roommate_name: str
    fixed_events: List[FixedEvent]
    flexible_events: List[FlexibleEvent]

class Scheduler(BaseModel):
    roommate_a: Schedule 
    roommate_b: Schedule

