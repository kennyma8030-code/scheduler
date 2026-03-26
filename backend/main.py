from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.models import Scheduler, Schedule, FixedEvent, FlexibleEvent, Scheduler_Weekly
from backend.algorithm import ScheduleOptimizer
from backend.PreferenceParser import PreferenceParser
from backend.EventClassifier import EventClassifier

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/analyze/day")
def analyze_day(request: Scheduler, text: str):
    schedule_a = request.roommate_a
    schedule_b = request.roommate_b

    fixed_schedule_a = ScheduleOptimizer.fixed(schedule_a)
    fixed_schedule_b = ScheduleOptimizer.fixed(schedule_b)

    free_hours_a = ScheduleOptimizer.available_flexible(schedule_a)
    free_hours_b = ScheduleOptimizer.available_flexible(schedule_b)

    combinations_a = ScheduleOptimizer.combinations(schedule_a.flexible_events, free_hours_a, fixed_schedule_a)
    combinations_b = ScheduleOptimizer.combinations(schedule_b.flexible_events, free_hours_b, fixed_schedule_b)

    parser = PreferenceParser()
    constraints_JSON = parser.parse(
        text,
        request.roommate_a.fixed_events + request.roommate_a.flexible_events,
        request.roommate_b.fixed_events + request.roommate_b.flexible_events,
    )

    all_events_a = request.roommate_a.fixed_events + request.roommate_a.flexible_events
    all_events_b = request.roommate_b.fixed_events + request.roommate_b.flexible_events
    constraints = ScheduleOptimizer.constraint_factory(constraints_JSON, all_events_a, all_events_b)

    output = ScheduleOptimizer.best_schedules(combinations_a, combinations_b, constraints)

    all_names = list({e.name for e in all_events_a + all_events_b})
    categories = EventClassifier().classify(all_names)

    return {"results": output["results"], "stats": output["stats"], "constraints": constraints_JSON, "categories": categories}

@app.post("/analyze/week")
def analyze_week(request: Scheduler_Weekly, text: str):
    schedule_a = request.roommate_a
    schedule_b = request.roommate_b

    combinations_a = ScheduleOptimizer.combinations_weekly(schedule_a)
    combinations_b = ScheduleOptimizer.combinations_weekly(schedule_b)

    parser = PreferenceParser()
    constraints_JSON = parser.parse(
        text,
        request.roommate_a.fixed_events + request.roommate_a.flexible_events,
        request.roommate_b.fixed_events + request.roommate_b.flexible_events,
    )

    all_events_a = request.roommate_a.fixed_events + request.roommate_a.flexible_events
    all_events_b = request.roommate_b.fixed_events + request.roommate_b.flexible_events
    constraints = ScheduleOptimizer.constraint_factory(constraints_JSON, all_events_a, all_events_b)

    output = ScheduleOptimizer.best_schedules_weekly(combinations_a, combinations_b, constraints)

    all_names = list({e.name for e in all_events_a + all_events_b})
    categories = EventClassifier().classify(all_names)

    return {"results": output, "constraints": constraints_JSON, "categories": categories}




