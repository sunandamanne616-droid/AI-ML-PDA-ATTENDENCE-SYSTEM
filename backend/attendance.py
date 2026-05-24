from datetime import date, datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.auth import get_db, require_roles, get_current_user
from backend.models import Student, Attendance, User, TimetableSlot, FacultyLog, AlertLog
from backend.excel_register import update_subject_excel

router = APIRouter(prefix="/attendance", tags=["Attendance"])

class MarkAttendanceIn(BaseModel):
    semester: int
    subject: str
    day: Optional[date] = None
    present_roll_nos: List[str] = []

@router.post("/mark")
def mark_attendance(
    payload: MarkAttendanceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod")),
):
    day = payload.day or date.today()
    students = db.query(Student).filter(Student.semester == payload.semester).all()
    if not students:
        raise HTTPException(status_code=404, detail="No students found for this semester")

    present_set = set(str(x).strip() for x in payload.present_roll_nos)
    statuses: Dict[str, str] = {}
    notifications = []

    for st in students:
        roll = str(st.roll_no)
        status = "P" if roll in present_set else "A"
        statuses[roll] = status

        existing = (
            db.query(Attendance)
            .filter(Attendance.roll_no == roll, Attendance.subject == payload.subject, Attendance.day == day)
            .first()
        )
        if existing:
            existing.status = status
            existing.marked_by = user.username
        else:
            db.add(Attendance(
                roll_no=roll, name=st.name, semester=payload.semester,
                subject=payload.subject, day=day, status=status,
                marked_by=user.username,
            ))

        # Calculate average for this student
        total = db.query(Attendance).filter(Attendance.roll_no == roll, Attendance.subject == payload.subject).count() + (0 if existing else 1)
        present_count = db.query(Attendance).filter(Attendance.roll_no == roll, Attendance.subject == payload.subject, Attendance.status == "P").count()
        if not existing and status == "P":
            present_count += 1
        avg = round((present_count / total * 100), 1) if total > 0 else 0

        notifications.append({
            "name": st.name, "roll_no": roll, "email": st.email,
            "phone": st.phone, "status": status, "average": avg,
        })

    db.commit()

    # Update excel
    update_subject_excel(
        semester=payload.semester, subject=payload.subject,
        students=[{"roll_no": s.roll_no, "name": s.name} for s in students],
        day=day, statuses=statuses,
    )

    # Send notifications in background
    try:
        from backend.notification import notify_attendance
        for n in notifications:
            notify_attendance(
                student_name=n["name"], roll_no=n["roll_no"],
                subject=payload.subject, date_str=day.isoformat(),
                status=n["status"], email=n["email"], phone=n["phone"],
                average=n["average"],
            )
    except Exception as e:
        print(f"[NOTIFY-ERROR] {e}")

    return {
        "message": "attendance marked",
        "semester": payload.semester,
        "subject": payload.subject,
        "day": day.isoformat(),
        "marked_by": user.username,
        "present": len(present_set & set(str(s.roll_no) for s in students)),
        "absent": len(students) - len(present_set & set(str(s.roll_no) for s in students)),
        "total": len(students),
    }

@router.get("/summary")
def daily_summary(
    day: date, semester: int, subject: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod", "principal")),
):
    q = db.query(Attendance).filter(
        Attendance.day == day, Attendance.semester == semester, Attendance.subject == subject,
    )
    total = q.count()
    present = q.filter(Attendance.status == "P").count()
    return {"day": day.isoformat(), "semester": semester, "subject": subject,
            "total": total, "present": present, "absent": total - present}

@router.get("/student/my-attendance")
def my_attendance(
    subject: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("student")),
):
    roll_no = user.username
    st = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student profile not found")

    q = db.query(Attendance).filter(Attendance.roll_no == roll_no)
    if subject:
        q = q.filter(Attendance.subject == subject)
    records = q.order_by(Attendance.day.asc()).all()
    total = len(records)
    present = sum(1 for r in records if r.status == "P")
    percentage = round((present / total) * 100, 2) if total else 0.0

    # Subject-wise breakdown
    subjects = {}
    for r in records:
        if r.subject not in subjects:
            subjects[r.subject] = {"total": 0, "present": 0}
        subjects[r.subject]["total"] += 1
        if r.status == "P":
            subjects[r.subject]["present"] += 1

    subject_breakdown = []
    for subj, data in subjects.items():
        avg = round((data["present"] / data["total"]) * 100, 2) if data["total"] else 0
        subject_breakdown.append({
            "subject": subj, "total": data["total"],
            "present": data["present"], "absent": data["total"] - data["present"],
            "percentage": avg, "below_75": avg < 75,
        })

    return {
        "roll_no": st.roll_no, "name": st.name,
        "total_classes": total, "present": present,
        "absent": total - present, "percentage": percentage,
        "below_75": percentage < 75,
        "subject_breakdown": subject_breakdown,
        "records": [
            {"day": r.day.isoformat(), "subject": r.subject, "status": r.status, "marked_by": r.marked_by}
            for r in records
        ],
    }

@router.get("/averages")
def get_averages(
    semester: int, subject: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod", "principal")),
):
    students = db.query(Student).filter(Student.semester == semester).all()
    result = []
    for st in students:
        records = db.query(Attendance).filter(
            Attendance.roll_no == st.roll_no, Attendance.subject == subject
        ).all()
        total = len(records)
        present = sum(1 for r in records if r.status == "P")
        avg = round((present / total) * 100, 2) if total else 0
        result.append({
            "roll_no": st.roll_no, "name": st.name,
            "total": total, "present": present, "absent": total - present,
            "percentage": avg, "below_75": avg < 75,
        })
    overall = round(sum(r["percentage"] for r in result) / len(result), 2) if result else 0
    return {"students": result, "overall_average": overall, "semester": semester, "subject": subject}

@router.get("/student-detail")
def student_detail(
    roll_no: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod", "principal")),
):
    st = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not st:
        raise HTTPException(404, "Student not found")

    records = db.query(Attendance).filter(Attendance.roll_no == roll_no).order_by(Attendance.day.asc()).all()
    subjects = {}
    for r in records:
        if r.subject not in subjects:
            subjects[r.subject] = {"total": 0, "present": 0}
        subjects[r.subject]["total"] += 1
        if r.status == "P":
            subjects[r.subject]["present"] += 1

    breakdown = []
    for subj, data in subjects.items():
        avg = round((data["present"] / data["total"]) * 100, 2) if data["total"] else 0
        breakdown.append({"subject": subj, "total": data["total"], "present": data["present"],
                          "absent": data["total"] - data["present"], "percentage": avg})

    total = len(records)
    present = sum(1 for r in records if r.status == "P")
    return {
        "roll_no": st.roll_no, "name": st.name, "semester": st.semester,
        "overall_total": total, "overall_present": present,
        "overall_percentage": round((present / total) * 100, 2) if total else 0,
        "subject_breakdown": breakdown,
        "records": [{"day": r.day.isoformat(), "subject": r.subject, "status": r.status} for r in records],
    }

# ── Attendance Register Grid (date-wise) ─────────────────

@router.get("/register")
def attendance_register(
    semester: int, subject: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod", "principal")),
):
    """Returns date-wise register grid for a subject."""
    students = db.query(Student).filter(Student.semester == semester).order_by(Student.roll_no).all()
    records = db.query(Attendance).filter(
        Attendance.subject == subject, Attendance.semester == semester
    ).order_by(Attendance.day).all()

    # Collect unique dates
    dates = sorted(set(r.day.isoformat() for r in records))

    # Build grid: {roll_no: {date: status}}
    grid = {}
    for r in records:
        if r.roll_no not in grid:
            grid[r.roll_no] = {}
        grid[r.roll_no][r.day.isoformat()] = r.status

    rows = []
    for st in students:
        total = sum(1 for d in dates if st.roll_no in grid and d in grid[st.roll_no])
        present = sum(1 for d in dates if grid.get(st.roll_no, {}).get(d) == "P")
        pct = round((present / total) * 100, 1) if total > 0 else 0
        rows.append({
            "roll_no": st.roll_no, "name": st.name,
            "attendance": {d: grid.get(st.roll_no, {}).get(d, "-") for d in dates},
            "total": total, "present": present,
            "absent": total - present, "percentage": pct,
            "below_75": pct < 75,
        })

    return {"dates": dates, "students": rows, "semester": semester, "subject": subject}

# ── Override Attendance (HOD) ─────────────────────────────

class OverrideIn(BaseModel):
    roll_no: str
    subject: str
    day: date
    status: str  # "P" or "A"

@router.post("/override")
def override_attendance(
    payload: OverrideIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod")),
):
    existing = db.query(Attendance).filter(
        Attendance.roll_no == payload.roll_no,
        Attendance.subject == payload.subject,
        Attendance.day == payload.day,
    ).first()

    if existing:
        existing.status = payload.status
        existing.marked_by = f"Override ({user.username})"
    else:
        st = db.query(Student).filter(Student.roll_no == payload.roll_no).first()
        if not st:
            raise HTTPException(404, "Student not found")
        db.add(Attendance(
            roll_no=payload.roll_no, name=st.name, semester=st.semester,
            subject=payload.subject, day=payload.day, status=payload.status,
            marked_by=f"Override ({user.username})",
        ))

    db.commit()
    return {"message": f"{payload.roll_no} marked {payload.status} for {payload.subject} on {payload.day}"}

# ── Below 75% Students ───────────────────────────────────

@router.get("/below-75")
def below_75_students(
    semester: Optional[int] = None,
    subject: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod", "principal")),
):
    q = db.query(Student)
    if semester:
        q = q.filter(Student.semester == semester)
    students = q.all()

    result = []
    for st in students:
        aq = db.query(Attendance).filter(Attendance.roll_no == st.roll_no)
        if subject:
            aq = aq.filter(Attendance.subject == subject)
        records = aq.all()
        total = len(records)
        present = sum(1 for r in records if r.status == "P")
        pct = round((present / total) * 100, 1) if total > 0 else 0
        if pct < 75:
            # Subject breakdown
            subj_data = {}
            for r in records:
                if r.subject not in subj_data:
                    subj_data[r.subject] = {"total": 0, "present": 0}
                subj_data[r.subject]["total"] += 1
                if r.status == "P":
                    subj_data[r.subject]["present"] += 1
            subj_list = []
            for s, d in subj_data.items():
                sp = round((d["present"] / d["total"]) * 100, 1) if d["total"] else 0
                subj_list.append({"subject": s, "total": d["total"], "present": d["present"], "percentage": sp})

            result.append({
                "roll_no": st.roll_no, "name": st.name, "semester": st.semester,
                "email": st.email, "phone": st.phone,
                "total": total, "present": present, "percentage": pct,
                "subjects": subj_list,
            })

    result.sort(key=lambda x: x["percentage"])
    return {"count": len(result), "students": result}

# ── All Subjects (for filters) ────────────────────────────

@router.get("/all-subjects")
def all_subjects(
    semester: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod", "principal")),
):
    q = db.query(TimetableSlot)
    if semester:
        q = q.filter(TimetableSlot.semester == semester)
    slots = q.all()
    subjects = sorted(set(s.subject for s in slots if s.subject))
    semesters = sorted(set(s.semester for s in slots if s.semester))
    faculties = sorted(set(s.faculty_username for s in slots if s.faculty_username))
    return {"subjects": subjects, "semesters": semesters, "faculties": faculties}

# ── Faculty Activity Log ──────────────────────────────────

@router.get("/faculty-log")
def get_faculty_log(
    faculty: Optional[str] = None,
    semester: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "principal")),
):
    q = db.query(FacultyLog)
    if faculty:
        q = q.filter(FacultyLog.faculty_username == faculty)
    if semester:
        q = q.filter(FacultyLog.semester == semester)
    if from_date:
        q = q.filter(FacultyLog.day >= date.fromisoformat(from_date))
    if to_date:
        q = q.filter(FacultyLog.day <= date.fromisoformat(to_date))
    logs = q.order_by(FacultyLog.day.desc()).limit(200).all()
    return [{
        "id": l.id, "faculty": l.faculty_username, "subject": l.subject,
        "semester": l.semester, "day": l.day.isoformat(),
        "scheduled_start": l.scheduled_start, "scheduled_end": l.scheduled_end,
        "actual_start": l.actual_start.strftime("%H:%M") if l.actual_start else None,
        "actual_end": l.actual_end.strftime("%H:%M") if l.actual_end else None,
        "duration": l.duration_minutes, "present": l.present_count,
        "absent": l.absent_count, "total": l.total_count,
        "mode": l.mode, "status": l.status, "remark": l.remark,
    } for l in logs]

class FacultyLogUpdateIn(BaseModel):
    status: str  # "completed", "missed", "on_leave", "other_duty", "cancelled"
    remark: Optional[str] = None

@router.put("/faculty-log/{log_id}")
def update_faculty_log(
    log_id: int,
    payload: FacultyLogUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod")),
):
    log = db.query(FacultyLog).filter(FacultyLog.id == log_id).first()
    if not log:
        raise HTTPException(404, "Log not found")
    log.status = payload.status
    if payload.remark is not None:
        log.remark = payload.remark
    db.commit()
    return {"message": "Faculty log updated"}

# ── Daily Class Summary ───────────────────────────────────

@router.get("/daily-summary")
def daily_class_summary(
    day: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "principal")),
):
    from datetime import datetime as dt
    target = date.fromisoformat(day) if day else date.today()
    day_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
    day_name = day_map.get(target.weekday(), "")

    scheduled = db.query(TimetableSlot).filter(TimetableSlot.day_name == day_name).all()
    logs = db.query(FacultyLog).filter(FacultyLog.day == target).all()
    log_map = {(l.faculty_username, l.subject): l for l in logs}

    classes = []
    held = 0
    for s in scheduled:
        log = log_map.get((s.faculty_username, s.subject))
        was_held = log is not None and log.status == "completed"
        if was_held:
            held += 1
        classes.append({
            "subject": s.subject, "faculty": s.faculty_username,
            "semester": s.semester, "room": s.room,
            "scheduled": f"{s.start_time}-{s.end_time}",
            "held": was_held,
            "status": log.status if log else "missed",
            "present": log.present_count if log else 0,
            "total": log.total_count if log else 0,
            "remark": log.remark if log else None,
        })

    return {
        "date": target.isoformat(), "day": day_name,
        "total_scheduled": len(scheduled), "classes_held": held,
        "classes_missed": len(scheduled) - held,
        "classes": classes,
    }

# ── Download Register as CSV ──────────────────────────────

@router.get("/register/csv")
def download_register_csv(
    semester: int, subject: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod", "principal")),
):
    import io, csv
    from fastapi.responses import StreamingResponse

    data = attendance_register(semester, subject, db, user)
    output = io.StringIO()
    writer = csv.writer(output)
    header = ["Roll No", "Name"] + data["dates"] + ["Total", "Present", "Absent", "%"]
    writer.writerow(header)
    for s in data["students"]:
        row = [s["roll_no"], s["name"]]
        row += [s["attendance"].get(d, "-") for d in data["dates"]]
        row += [s["total"], s["present"], s["absent"], s["percentage"]]
        writer.writerow(row)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{subject}_Sem{semester}_Register.csv"'}
    )

# ── Download Register as Formatted Excel ─────────────────

@router.get("/register/excel")
def download_register_excel(
    semester: int, subject: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod", "principal")),
):
    """
    Generate a fully formatted Excel with subject info header, colour-coded P/A grid,
    per-student totals and percentage, and class average footer.
    """
    from fastapi.responses import FileResponse

    data = attendance_register(semester, subject, db, user)

    slot = db.query(TimetableSlot).filter(
        TimetableSlot.subject == subject,
        TimetableSlot.semester == semester,
    ).first()

    faculty_name  = slot.faculty_username if slot else "Not assigned"
    session_time  = f"{slot.start_time} - {slot.end_time}" if slot else "Not set"
    room          = (slot.room if slot else None) or "AIML-LAB"
    subject_code  = subject[:8].upper()

    faculty_user = None
    if slot and slot.faculty_username:
        faculty_user = db.query(User).filter(User.username == slot.faculty_username).first()
    faculty_display = faculty_name

    students_with_section = []
    for s in data["students"]:
        st_db = db.query(Student).filter(Student.roll_no == s["roll_no"]).first()
        s["section"] = getattr(st_db, "section", "A") or "A"
        students_with_section.append(s)

    path = generate_subject_excel(
        semester=semester,
        subject=subject,
        subject_code=subject_code,
        faculty_name=faculty_display,
        session_time=session_time,
        room=room,
        dept="AIML",
        students=students_with_section,
        dates=data["dates"],
    )

    return FileResponse(
        path=str(path),
        filename=f"{subject}_Sem{semester}_Register.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── Shortage Report API Routes ────────────────────────────

@router.post("/shortage-report/send")
async def send_shortage_report_now(
    semester: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "principal")),
):
    """
    Manually trigger the shortage report email to HOD/Principal.
    Also called automatically by the scheduler at 8 AM daily.
    """
    from backend.scheduler import send_shortage_report
    result = await send_shortage_report(
        db,
        semester=semester,
        triggered_by=f"Manual — by {user.username}"
    )
    return result

@router.get("/shortage-report/last-sent")
def shortage_report_last_sent(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "principal", "faculty")),
):
    """Return when the last shortage report was sent."""
    last = db.query(AlertLog).filter(
        AlertLog.alert_type == "shortage_report"
    ).order_by(AlertLog.created_at.desc()).first()

    if not last:
        return {"last_sent": None, "sent_to": None}

    return {
        "last_sent": last.created_at.strftime("%d %b %Y at %I:%M %p"),
        "sent_to": last.sent_to,
        "message": last.message,
    }
