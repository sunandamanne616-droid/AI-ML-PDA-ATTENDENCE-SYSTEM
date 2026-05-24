
"""
Fix: Create login accounts for ALL students who don't have one yet.
Run this once: python fix_student_logins.py
"""
from backend.database import Base, engine, SessionLocal
from backend.models import User, Student
from backend.auth import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Get all students
students = db.query(Student).order_by(Student.roll_no).all()
print(f"Total students in database: {len(students)}\n")

created = 0
skipped = 0

for st in students:
    existing_user = db.query(User).filter(User.username == st.roll_no).first()
    if existing_user:
        print(f"  ⏭ {st.roll_no} ({st.name}) — login already exists")
        skipped += 1
    else:
        db.add(User(
            username=st.roll_no,
            hashed_password=hash_password("student123"),
            role="student",
            email=st.email,
        ))
        print(f"  ✅ {st.roll_no} ({st.name}) — login CREATED")
        created += 1

db.commit()
db.close()

print(f"\n{'='*50}")
print(f"✅ Done! Created {created} new logins, skipped {skipped} existing.")
print(f"{'='*50}")
print(f"\nAll students can now login with:")
print(f"  Username: their roll number (e.g. 3PD22AI001)")
print(f"  Password: student123")
