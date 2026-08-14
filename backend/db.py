from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

engine = create_engine("sqlite:///app.db")
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Schedule(Base):
    __tablename__ = "Schedules"
    id = Column(Integer, primary_key=True)
    sched = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now())

class ScheduleWeekly(Base):
    __tablename__ = "Schedules_Weekly"
    id = Column(Integer, primary_key=True)
    scheds = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now())

def saveDaily(result):
    db = SessionLocal()
    row = Schedule(sched=result)
    db.add(row)
    db.commit()
    db.refresh(row)
    db.close()
    return row.id

def saveWeekly(result):
    db = SessionLocal()
    row = ScheduleWeekly(scheds=result)
    db.add(row)
    db.commit()
    db.refresh(row)
    db.close()
    return row.id

def loadDaily(id):
    db = SessionLocal()
    row = db.query(Schedule).filter(Schedule.id == id).first()
    db.close()
    return row.sched if row else None

def loadWeekly(id):
    db = SessionLocal()
    row = db.query(ScheduleWeekly).filter(ScheduleWeekly.id == id).first()
    db.close()
    return row.scheds if row else None

def listSchedules():
    db = SessionLocal()
    daily  = [{"id": r.id, "type": "daily",  "created_at": r.created_at.isoformat() if r.created_at is not None else None} for r in db.query(Schedule).all()]
    weekly = [{"id": r.id, "type": "weekly", "created_at": r.created_at.isoformat() if r.created_at is not None else None} for r in db.query(ScheduleWeekly).all()]
    db.close()
    return sorted(daily + weekly, key=lambda x: x["created_at"] or "", reverse=True)

Base.metadata.create_all(engine)