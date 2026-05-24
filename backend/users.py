from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from backend.auth import get_db, require_roles
from backend.models import Student, User, Attendance

router = APIRouter(prefix="/students", tags=["Students"])

class StudentIn(BaseModel):
    roll_no: str
    name: str
    semester: int
    dept: str = "AIML"
    email: Optional[str] = None
    phone: Optional[str] = None

@router.post("/add")
def add_student(
    payload: StudentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty")),
):
    exists = db.query(Student).filter(Student.roll_no == payload.roll_no).first()
    if exists:
        raise HTTPException(status_code=400, detail="Student already exists")
    st = Student(**payload.model_dump())
    db.add(st)

    # Auto-create login account for student (username=roll_no, password=student123)
    from backend.auth import hash_password
    existing_user = db.query(User).filter(User.username == payload.roll_no).first()
    if not existing_user:
        db.add(User(
            username=payload.roll_no,
            hashed_password=hash_password("student123"),
            role="student",
            email=payload.email,
        ))

    db.commit()
    db.refresh(st)
    return {"message": "student created", "roll_no": st.roll_no, "name": st.name}

@router.get("/list")
def list_students(
    semester: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty", "principal")),
):
    students = db.query(Student).filter(Student.semester == semester).order_by(Student.roll_no.asc()).all()
    return [{"roll_no": s.roll_no, "name": s.name, "dept": s.dept,
             "semester": s.semester, "email": s.email, "phone": s.phone} for s in students]

@router.delete("/delete/{roll_no}")
def delete_student(
    roll_no: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty")),
):
    st = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not st:
        raise HTTPException(404, "Student not found")
    db.query(Attendance).filter(Attendance.roll_no == roll_no).delete()
    db.delete(st)
    db.commit()
    return {"message": f"Student {roll_no} deleted"}

@router.put("/update/{roll_no}")
def update_student(
    roll_no: str,
    payload: StudentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty")),
):
    st = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not st:
        raise HTTPException(404, "Student not found")
    st.name = payload.name
    st.semester = payload.semester
    st.dept = payload.dept
    if payload.email:
        st.email = payload.email
    if payload.phone:
        st.phone = payload.phone
    db.commit()
    return {"message": f"Student {roll_no} updated"}

# ── Faculty Management (HOD only) ─────────────────────────

class FacultyIn(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

@router.post("/faculty/add", tags=["Faculty"])
def add_faculty(
    payload: FacultyIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod")),
):
    from backend.auth import hash_password
    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(400, "Username already exists")
    u = User(
        username=payload.username.strip(),
        hashed_password=hash_password(payload.password),
        role="faculty",
        email=payload.email.strip() if payload.email else None,
    )
    db.add(u)
    db.commit()
    return {"message": f"Faculty '{payload.username}' created", "username": payload.username}

@router.get("/faculty/list", tags=["Faculty"])
def list_faculty(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "principal")),
):
    faculties = db.query(User).filter(User.role == "faculty").order_by(User.username).all()
    return [{"username": f.username, "email": f.email} for f in faculties]

@router.delete("/faculty/delete/{username}", tags=["Faculty"])
def delete_faculty(
    username: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod")),
):
    f = db.query(User).filter(User.username == username, User.role == "faculty").first()
    if not f:
        raise HTTPException(404, "Faculty not found")
    db.delete(f)
    db.commit()
    return {"message": f"Faculty '{username}' deleted"}

class FacultyEditIn(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None

@router.put("/faculty/edit/{username}", tags=["Faculty"])
def edit_faculty(
    username: str,
    payload: FacultyEditIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod")),
):
    from backend.auth import hash_password
    f = db.query(User).filter(User.username == username, User.role == "faculty").first()
    if not f:
        raise HTTPException(404, "Faculty not found")
    if payload.email is not None:
        f.email = payload.email.strip()
    if payload.password:
        f.hashed_password = hash_password(payload.password)
    db.commit()
    return {"message": f"Faculty '{username}' updated"}


