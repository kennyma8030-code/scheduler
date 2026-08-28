from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.models import Scheduler, Schedule, FixedEvent, FlexibleEvent, Scheduler_Weekly
from backend.algorithm import ScheduleOptimizer
from backend.PreferenceParser import PreferenceParser
from backend.EventClassifier import EventClassifier
from backend.CanvasImporter import CanvasImporter
from backend.GoogleCalendarImporter import GoogleCalendarImporter
from backend.db import saveDaily, loadDaily, saveWeekly, loadWeekly, listSchedules
from backend.class_scheduler.api import router as course_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# The course schedule generator — the product this app is becoming. The
# roommate endpoints below it are legacy and slated for removal.
app.include_router(course_router)

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
    saveDaily(output)

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
    saveWeekly(output)

    all_names = list({e.name for e in all_events_a + all_events_b})
    categories = EventClassifier().classify(all_names)

    return {"results": output, "constraints": constraints_JSON, "categories": categories}

@app.get("/schedules")
def get_schedules():
    return listSchedules()

@app.get("/load/daily")
def load_daily(id: int):
    return loadDaily(id)

@app.get("/load/weekly")
def load_weekly(id: int):
    return loadWeekly(id)


# ── Canvas import ─────────────────────────────────────────────────────────────
class CanvasDayRequest(BaseModel):
    url: str
    date: str        # ISO date e.g. "2026-03-28"

class CanvasWeekRequest(BaseModel):
    url: str
    from_date: str | None = None

@app.post("/import/canvas/day")
def import_canvas_day(request: CanvasDayRequest):
    try:
        events = CanvasImporter().fetch_day(request.url, request.date)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/import/canvas/week")
def import_canvas_week(request: CanvasWeekRequest):
    try:
        events = CanvasImporter().fetch_week(request.url, request.from_date)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Google Calendar import ────────────────────────────────────────────────────
class GoogleDayRequest(BaseModel):
    url: str
    date: str

class GoogleWeekRequest(BaseModel):
    url: str
    from_date: str | None = None

@app.post("/import/google/day")
def import_google_day(request: GoogleDayRequest):
    try:
        events = GoogleCalendarImporter().fetch_day(request.url, request.date)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/import/google/week")
def import_google_week(request: GoogleWeekRequest):
    try:
        events = GoogleCalendarImporter().fetch_week(request.url, request.from_date)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/import/google/debug")
def import_google_debug(request: GoogleWeekRequest):
    import recurring_ical_events
    from icalendar import Calendar
    import httpx
    from datetime import date, timedelta
    res = httpx.get(request.url, timeout=15, follow_redirects=True)
    cal = Calendar.from_ical(res.content)
    d = date.fromisoformat(request.from_date) if request.from_date else date.today()
    monday = d - timedelta(days=d.weekday())
    out = []
    for day_idx in range(7):
        day = monday + timedelta(days=day_idx)
        for e in recurring_ical_events.of(cal).at(day):
            start = e["DTSTART"].dt
            out.append({
                "day_idx": day_idx,
                "date": str(day),
                "summary": str(e.get("SUMMARY", "")),
                "dtstart": str(start),
                "has_rrule": "RRULE" in e,
                "categories": str(e.get("CATEGORIES", "")),
            })
    return {"events": out, "week_start": str(monday)}




