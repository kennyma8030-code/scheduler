from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import Scheduler
from algorithm import ScheduleOptimizer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/analyze")
def analyze(request: Scheduler):
    a_schedule = request.roommate_a
    b_schedule = request.roommate_b
    
    a_fixed = ScheduleOptimizer.fixed(a_schedule)
    b_fixed = ScheduleOptimizer.fixed(b_schedule)
   
    available_a = ScheduleOptimizer.available_flexible(a_schedule)
    available_b = ScheduleOptimizer.available_flexible(b_schedule)

    combinations_a = ScheduleOptimizer.combinations(request.roommate_a.flexible_events, available_a, a_fixed)
    combinations_b = ScheduleOptimizer.combinations(request.roommate_b.flexible_events, available_b, b_fixed)

    top_10 = ScheduleOptimizer.best_schedules(combinations_a, combinations_b)

    return {"results": top_10} 

   
