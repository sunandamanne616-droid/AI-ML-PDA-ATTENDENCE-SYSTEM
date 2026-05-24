"""
Run this once to create default users for all 4 roles.
Usage: python setup_users.py
"""
from backend.database import Base, engine, SessionLocal
from backend.models import User, Student, TimetableSlot
from backend.auth import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── Default Users ─────────────────────────
users = [
    {"username": "faculty1", "password": "faculty123", "role": "faculty", "email": "faculty@aiml.edu"},
    {"username": "hod1", "password": "hod123", "role": "hod", "email": "hod@aiml.edu"},
    {"username": "principal1", "password": "principal123", "role": "principal", "email": "principal@aiml.edu"},
    # Students — username = roll number
    {"username": "3PD22AI001", "password": "student123", "role": "student", "email": "student1@aiml.edu"},
    {"username": "3PD22AI002", "password": "student123", "role": "student", "email": "student2@aiml.edu"},
    {"username": "3PD22AI003", "password": "student123", "role": "student", "email": "student3@aiml.edu"},
]

print("Creating users...")
for u in users:
    existing = db.query(User).filter(User.username == u["username"]).first()
    if existing:
        print(f"  ⏭ {u['username']} ({u['role']}) — already exists")
        continue
    db.add(User(
        username=u["username"],
        hashed_password=hash_password(u["password"]),
        role=u["role"],
        email=u.get("email"),
    ))
    print(f"  ✅ {u['username']} ({u['role']}) — created")

# ── Default Students ──────────────────────
students = [
    {"roll_no": "3PD22AI001", "name": "STUDENT ONE", "semester": 8, "email": "student1@aiml.edu"},
    {"roll_no": "3PD22AI002", "name": "STUDENT TWO", "semester": 8, "email": "student2@aiml.edu"},
    {"roll_no": "3PD22AI003", "name": "STUDENT THREE", "semester": 8, "email": "student3@aiml.edu"},
]

print("\nCreating students...")
for s in students:
    existing = db.query(Student).filter(Student.roll_no == s["roll_no"]).first()
    if existing:
        print(f"  ⏭ {s['roll_no']} — already exists")
        continue
    db.add(Student(**s))
    print(f"  ✅ {s['roll_no']} ({s['name']})")

# ── Default Timetable ────────────────────
slots = [
    {"day_name": "MON", "start_time": "09:00", "end_time": "10:00", "semester": 8, "subject": "BDA", "faculty_username": "faculty1"},
    {"day_name": "MON", "start_time": "10:00", "end_time": "11:00", "semester": 8, "subject": "CC", "faculty_username": "faculty1"},
    {"day_name": "TUE", "start_time": "09:00", "end_time": "10:00", "semester": 8, "subject": "BDA", "faculty_username": "faculty1"},
    {"day_name": "WED", "start_time": "09:00", "end_time": "10:00", "semester": 8, "subject": "FLAT", "faculty_username": "faculty1"},
]

print("\nCreating timetable...")
for s in slots:
    existing = db.query(TimetableSlot).filter(
        TimetableSlot.day_name == s["day_name"],
        TimetableSlot.start_time == s["start_time"],
        TimetableSlot.subject == s["subject"],
    ).first()
    if existing:
        print(f"  ⏭ {s['day_name']} {s['start_time']} {s['subject']} — exists")
        continue
    db.add(TimetableSlot(**s))
    print(f"  ✅ {s['day_name']} {s['start_time']}-{s['end_time']} {s['subject']}")

db.commit()
db.close()

print("\n" + "=" * 50)
print("✅ Setup complete!")
print("=" * 50)
print("\nLogin credentials:")
print("  Faculty:   faculty1 / faculty123")
print("  HOD:       hod1 / hod123")
print("  Principal: principal1 / principal123")
print("  Student:   3PD22AI001 / student123")
print("\nStart server: python -m uvicorn backend.main:app --port 8002")
print("Dashboard:   http://localhost:8002/dashboard")
