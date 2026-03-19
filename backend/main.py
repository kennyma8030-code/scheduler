from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.models import Scheduler, Schedule, FixedEvent, FlexibleEvent
from backend.algorithm import ScheduleOptimizer
from backend.PreferenceParser import PreferenceParser

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/analyze")
def analyze(request: Scheduler, text: str):
    schedule_a = request.roommate_a
    schedule_b = request.roommate_b

    fixed_schedule_a = ScheduleOptimizer.fixed(schedule_a)
    fixed_schedule_b = ScheduleOptimizer.fixed(schedule_b)

    free_hours_a = ScheduleOptimizer.available_flexible(schedule_a)
    free_hours_b = ScheduleOptimizer.available_flexible(schedule_b)

    combinations_a = ScheduleOptimizer.combinations(schedule_a.flexible_events, free_hours_a, fixed_schedule_a)
    combinations_b = ScheduleOptimizer.combinations(schedule_b.flexible_events, free_hours_b, fixed_schedule_b)

    parser = PreferenceParser()
    constraints_JSON = parser.parse(text, request.roommate_a, request.roommate_b)

    top_schedules = ScheduleOptimizer.best_schedules(combinations_a, combinations_b, constraints_JSON)

    return {"results": top_schedules}


@app.get("/test-parser")
def test_parser():
    schedule_a = Schedule(
        roommate_name="Alex",
        fixed_events=[
            FixedEvent(name="morning_lecture", start=8, finish=10),
            FixedEvent(name="evening_class", start=18, finish=20),
        ],
        flexible_events=[
            FlexibleEvent(name="gym", duration=2, in_dorm=False),
            FlexibleEvent(name="nap", duration=1, in_dorm=True),
            FlexibleEvent(name="study", duration=3, in_dorm=True),
        ],
    )
    schedule_b = Schedule(
        roommate_name="Blake",
        fixed_events=[
            FixedEvent(name="work", start=9, finish=17),
        ],
        flexible_events=[
            FlexibleEvent(name="sleep", duration=8, in_dorm=True),
            FlexibleEvent(name="gaming", duration=2, in_dorm=True),
            FlexibleEvent(name="cooking", duration=1, in_dorm=True),
        ],
    )
    text = (
        "I absolutely cannot have my nap interrupted by Blake's gaming — "
        "it's non-negotiable. I also really prefer to study in the mornings before noon. "
        "It would be nice if we're both home for cooking. "
        "Blake's sleep should never overlap with Alex's gym."
    )
    parser = PreferenceParser()
    result = parser.parse(text, schedule_a.fixed_events + schedule_a.flexible_events,
                                schedule_b.fixed_events + schedule_b.flexible_events)
    return {"constraints": result}


@app.get("/test-score")
def test_score():
    schedule_a = Schedule(
        roommate_name="Alex",
        fixed_events=[
            FixedEvent(name="lecture",      start=9,  finish=11),
            FixedEvent(name="lab",          start=14, finish=16),
            FixedEvent(name="club_meeting", start=19, finish=20),
        ],
        flexible_events=[
            FlexibleEvent(name="gym",      duration=2, in_dorm=False),
            FlexibleEvent(name="study",    duration=3, in_dorm=True),
            FlexibleEvent(name="nap",      duration=1, in_dorm=True),
            FlexibleEvent(name="cooking",  duration=1, in_dorm=True),
        ],
    )
    schedule_b = Schedule(
        roommate_name="Blake",
        fixed_events=[
            FixedEvent(name="work",        start=10, finish=14),
            FixedEvent(name="night_class", start=18, finish=20),
        ],
        flexible_events=[
            FlexibleEvent(name="sleep",    duration=8, in_dorm=True),
            FlexibleEvent(name="gaming",   duration=2, in_dorm=True),
            FlexibleEvent(name="workout",  duration=1, in_dorm=False),
            FlexibleEvent(name="reading",  duration=2, in_dorm=True),
        ],
    )

    text = (
        "Alex's gym should never overlap with Blake's sleep — non-negotiable. "
        "Alex's nap should never overlap with Blake's gaming. "
        "I'd really prefer Alex's study doesn't overlap with Blake's reading. "
        "It would be nice if cooking and sleep don't overlap. "
        "It would be nice if we're not both home at the same time."
    )

    all_events_a = schedule_a.fixed_events + schedule_a.flexible_events
    all_events_b = schedule_b.fixed_events + schedule_b.flexible_events

    print("--- Step 1: Parsing preferences ---")
    parser = PreferenceParser()
    constraints_json = parser.parse(text, all_events_a, all_events_b)
    print(f"Constraints from AI: {len(constraints_json)}")
    for c in constraints_json:
        print(f"  {c}")

    print("--- Step 2: Building constraint objects ---")
    constraints = ScheduleOptimizer.constraint_factory(constraints_json, all_events_a, all_events_b)
    print(f"Constraint objects: {len(constraints)}")

    print("--- Step 3: Generating combinations ---")
    fixed_a  = ScheduleOptimizer.fixed(schedule_a)
    fixed_b  = ScheduleOptimizer.fixed(schedule_b)
    free_a   = ScheduleOptimizer.available_flexible(schedule_a)
    free_b   = ScheduleOptimizer.available_flexible(schedule_b)
    combos_a = ScheduleOptimizer.combinations(schedule_a.flexible_events, free_a, fixed_a)
    combos_b = ScheduleOptimizer.combinations(schedule_b.flexible_events, free_b, fixed_b)
    print(f"Combos A: {len(combos_a)}, Combos B: {len(combos_b)}, Total pairs: {len(combos_a) * len(combos_b)}")

    print("--- Step 4: Scoring ---")
    results = ScheduleOptimizer.best_schedules(combos_a, combos_b, constraints)
    print(f"Passing pairs: {len(results)}")

    stats = {}
    if results:
        import statistics
        scores = sorted(r["score"] for r in results)
        stats = {
            "min":    round(scores[0], 2),
            "max":    round(scores[-1], 2),
            "mean":   round(statistics.mean(scores), 2),
            "median": round(statistics.median(scores), 2),
            "stdev":  round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
            "q1":     round(statistics.quantiles(scores, n=4)[0], 2),
            "q3":     round(statistics.quantiles(scores, n=4)[2], 2),
        }
        print(f"Score stats: {stats}")

        sorted_results = sorted(results, key=lambda r: r["score"])
        median_idx = len(sorted_results) // 2

        for label, r in [("MIN", sorted_results[0]), ("MEDIAN", sorted_results[median_idx]), ("MAX", sorted_results[-1])]:
            print(f"\n--- {label} (score={round(r['score'], 2)}) ---")
            print(f"  Alex:  {r['roommate_a']}")
            print(f"  Blake: {r['roommate_b']}")

    return {
        "total_combos": len(combos_a) * len(combos_b),
        "passing_combos": len(results),
        "stats": stats,
        "results": results,
    }


