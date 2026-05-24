from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from backend.auth import get_db, require_roles, get_current_user
from backend.models import TimetableSlot, User

router = APIRouter(prefix="/timetable", tags=["Timetable"])

class SlotIn(BaseModel):
    day_name: str
    start_time: str
    end_time: str
    semester: int
    subject: str
    faculty_username: Optional[str] = None
    room: Optional[str] = "AIML-LAB-1"

@router.post("/add")
def add_slot(
    payload: SlotIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty")),
):
    slot = TimetableSlot(**payload.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {"message": "slot added", "id": slot.id}

@router.get("/")
def view_all(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty", "principal")),
):
    slots = db.query(TimetableSlot).order_by(TimetableSlot.day_name, TimetableSlot.start_time).all()
    return [
        {"id": s.id, "day": s.day_name, "start": s.start_time, "end": s.end_time,
         "semester": s.semester, "subject": s.subject,
         "faculty": s.faculty_username, "room": s.room}
        for s in slots
    ]

@router.get("/my-slots")
def my_slots(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty")),
):
    slots = db.query(TimetableSlot).filter(
        TimetableSlot.faculty_username == user.username
    ).order_by(TimetableSlot.day_name, TimetableSlot.start_time).all()
    return [
        {"id": s.id, "day": s.day_name, "start": s.start_time, "end": s.end_time,
         "semester": s.semester, "subject": s.subject, "room": s.room}
        for s in slots
    ]

@router.get("/current-slot")
def current_slot(db: Session = Depends(get_db)):
    now = datetime.now()
    day_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
    today = day_map.get(now.weekday(), "")
    current_time = now.strftime("%H:%M")

    slots = db.query(TimetableSlot).filter(TimetableSlot.day_name == today).all()
    for s in slots:
        if s.start_time <= current_time <= s.end_time:
            return {
                "found": True, "id": s.id, "day": s.day_name,
                "start": s.start_time, "end": s.end_time,
                "semester": s.semester, "subject": s.subject,
                "faculty": s.faculty_username, "room": s.room,
            }
    return {"found": False, "message": "No class scheduled right now"}

@router.delete("/{slot_id}")
def delete_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty")),
):
    slot = db.query(TimetableSlot).filter(TimetableSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(404, "Slot not found")
    db.delete(slot)
    db.commit()
    return {"message": "slot deleted"}

@router.put("/{slot_id}")
def update_slot(
    slot_id: int,
    payload: SlotIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty")),
):
    slot = db.query(TimetableSlot).filter(TimetableSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(404, "Slot not found")
    slot.day_name = payload.day_name
    slot.start_time = payload.start_time
    slot.end_time = payload.end_time
    slot.semester = payload.semester
    slot.subject = payload.subject
    slot.faculty_username = payload.faculty_username
    slot.room = payload.room
    db.commit()
    return {"message": "slot updated"}

@router.get("/my-subjects")
def my_subjects(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty")),
):
    """Return unique subjects + semesters assigned to this faculty via timetable."""
    slots = db.query(TimetableSlot).filter(
        TimetableSlot.faculty_username == user.username
    ).all()
    subjects = list(set(s.subject for s in slots if s.subject))
    semesters = list(set(s.semester for s in slots if s.semester))
    subjects.sort()
    semesters.sort()
    return {"subjects": subjects, "semesters": semesters, "username": user.username}

