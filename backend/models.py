from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, Float, Text, UniqueConstraint
from backend.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin | faculty | hod | student | principal
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    roll_no = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    dept = Column(String, nullable=False, default="AIML")
    semester = Column(Integer, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    roll_no = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    semester = Column(Integer, index=True, nullable=False)
    subject = Column(String, index=True, nullable=False)
    day = Column(Date, index=True, nullable=False)
    status = Column(String, nullable=False)  # "P" or "A"
    marked_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint("roll_no", "subject", "day", name="uq_attendance_roll_subject_day"),
    )

class TimetableSlot(Base):
    __tablename__ = "timetable_slots"
    id = Column(Integer, primary_key=True, index=True)
    day_name = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    semester = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    faculty_username = Column(String, nullable=True)
    room = Column(String, nullable=True, default="AIML-LAB-1")

class LiveClassStatus(Base):
    __tablename__ = "live_class_status"
    id = Column(Integer, primary_key=True, index=True)
    is_active = Column(Boolean, default=False)
    faculty_name = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    semester = Column(Integer, nullable=True)
    room = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    present_count = Column(Integer, default=0)
    camera_streaming = Column(Boolean, default=False)
    attendance_running = Column(Boolean, default=False)
    attendance_end_time = Column(DateTime, nullable=True)

class AlertLog(Base):
    __tablename__ = "alert_logs"
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String, nullable=False)  # "no_class", "low_attendance"
    message = Column(String, nullable=False)
    sent_to = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved = Column(Boolean, default=False)

class FacultyLog(Base):
    __tablename__ = "faculty_logs"
    id = Column(Integer, primary_key=True, index=True)
    faculty_username = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    semester = Column(Integer, nullable=False)
    day = Column(Date, nullable=False, index=True)
    scheduled_start = Column(String, nullable=True)
    scheduled_end = Column(String, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=0)
    present_count = Column(Integer, default=0)
    absent_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    mode = Column(String, default="manual")  # "manual" or "auto"
    status = Column(String, default="completed")  # "completed", "missed", "on_leave", "other_duty", "cancelled"
    remark = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class HolidayLog(Base):
    __tablename__ = "holiday_logs"
    id = Column(Integer, primary_key=True, index=True)
    day = Column(Date, nullable=False, index=True)
    reason = Column(String, nullable=False)  # "Holiday", "Event", "Mourning", "Other"
    subject = Column(String, nullable=True)  # None = all subjects, or specific subject
    semester = Column(Integer, nullable=True)  # None = all semesters
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

# ══════════════════════════════════════════════════════════
# NEW: Academic Calendar, Syllabus, Lesson Plan
# ══════════════════════════════════════════════════════════

class AcademicCalendar(Base):
    """Stores semester start/end dates."""
    __tablename__ = "academic_calendar"
    id = Column(Integer, primary_key=True, index=True)
    semester = Column(Integer, nullable=False, index=True)
    sem_start = Column(Date, nullable=False)
    sem_end = Column(Date, nullable=False)
    year = Column(Integer, nullable=False)                   # e.g. 2026
    label = Column(String, nullable=True)                    # e.g. "Even Sem 2025-26"
    working_days = Column(String, nullable=True)             # JSON: ["MON","TUE","WED","THU","FRI","SAT"]
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("semester", "year", name="uq_calendar_sem_year"),
    )

class Syllabus(Base):
    """Stores uploaded syllabus for each subject."""
    __tablename__ = "syllabi"
    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False, index=True)
    semester = Column(Integer, nullable=False, index=True)
    raw_text = Column(Text, nullable=True)                   # Full extracted text
    topics_json = Column(Text, nullable=True)                # JSON: [{unit, title, topics: [...], hours}]
    total_hours = Column(Integer, nullable=True)
    source_filename = Column(String, nullable=True)
    uploaded_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("subject", "semester", name="uq_syllabus_subj_sem"),
    )

class LessonPlan(Base):
    """Master lesson plan for a subject in a semester."""
    __tablename__ = "lesson_plans"
    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False, index=True)
    semester = Column(Integer, nullable=False, index=True)
    syllabus_id = Column(Integer, nullable=True)
    calendar_id = Column(Integer, nullable=True)
    total_classes = Column(Integer, nullable=True)
    plan_json = Column(Text, nullable=True)                  # Full AI-generated plan JSON
    status = Column(String, default="active")                # active | archived
    adjustments_count = Column(Integer, default=0)
    last_adjusted = Column(DateTime, nullable=True)
    generated_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("subject", "semester", "status", name="uq_plan_subj_sem_status"),
    )

class LessonPlanDay(Base):
    """Individual day in a lesson plan."""
    __tablename__ = "lesson_plan_days"
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    day_number = Column(Integer, nullable=False)             # Class number: 1, 2, 3...
    unit = Column(String, nullable=True)                     # Unit 1, Unit 2...
    topic = Column(String, nullable=False)
    subtopics = Column(Text, nullable=True)                  # Comma-separated or JSON
    teaching_method = Column(String, nullable=True)          # Lecture, Lab, Discussion, Quiz, Revision
    status = Column(String, default="planned")               # planned | completed | missed | rescheduled
    actual_topic = Column(String, nullable=True)             # What was actually covered (if different)
    remark = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=True)
