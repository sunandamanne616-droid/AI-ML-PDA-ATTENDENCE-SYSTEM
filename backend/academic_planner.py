"""
Academic Planner — Calendar, Syllabus, AI Lesson Plan Generator.
Uses Gemini API for: syllabus extraction (Vision) + lesson plan generation + auto-adjustment.
"""
import json, os, base64, traceback
from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

# ── Load .env so GEMINI_API_KEY is always available ──────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — key must be set in system env

from backend.auth import get_db, require_roles, get_current_user
from backend.models import (
    User, AcademicCalendar, Syllabus, LessonPlan, LessonPlanDay,
    TimetableSlot, FacultyLog, HolidayLog,
)

router = APIRouter(prefix="/planner", tags=["Academic Planner"])

GEMINI_MODEL = "gemini-2.0-flash"

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "syllabus_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_gemini_key():
    return os.getenv("GEMINI_API_KEY", "").strip()


# ══════════════════════════════════════════════════════════
# GEMINI API HELPER
# ══════════════════════════════════════════════════════════

def _call_gemini(prompt: str, image_b64: str = None, mime_type: str = None) -> str:
    """Call Gemini API with text or vision prompt."""
    import urllib.request, urllib.error

    GEMINI_API_KEY = _get_gemini_key()
    if not GEMINI_API_KEY:
        raise HTTPException(
            500,
            "GEMINI_API_KEY not set. Add GEMINI_API_KEY=your_key to your .env file. "
            "Get a free key at https://aistudio.google.com"
        )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    parts = []
    if image_b64 and mime_type:
        parts.append({"inline_data": {"mime_type": mime_type, "data": image_b64}})
    parts.append({"text": prompt})

    body = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192}
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        print(f"[GEMINI ERROR] {e.code}: {error_body[:500]}")
        if e.code == 400:
            raise HTTPException(502, f"Gemini bad request: {error_body[:300]}")
        elif e.code == 403:
            raise HTTPException(502, "Gemini API key invalid. Check your key at aistudio.google.com")
        elif e.code == 429:
            raise HTTPException(502, "Gemini rate limit hit. Wait a minute and try again.")
        raise HTTPException(502, f"Gemini API error {e.code}: {error_body[:200]}")
    except urllib.error.URLError as e:
        raise HTTPException(502, f"Network error reaching Gemini: {str(e)}")
    except Exception as e:
        print(f"[GEMINI ERROR] {e}")
        raise HTTPException(502, f"Gemini API error: {str(e)}")


def _clean_json(raw: str) -> str:
    """Strip markdown fences from AI response."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()
    return cleaned


# ══════════════════════════════════════════════════════════
# 1. ACADEMIC CALENDAR
# ══════════════════════════════════════════════════════════

class CalendarIn(BaseModel):
    semester: int
    sem_start: str
    sem_end: str
    year: int
    label: Optional[str] = ""
    working_days: Optional[str] = '["MON","TUE","WED","THU","FRI","SAT"]'


@router.get("/calendar")
def get_calendars(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cals = db.query(AcademicCalendar).order_by(AcademicCalendar.year.desc(), AcademicCalendar.semester).all()
    return [_cal_dict(c) for c in cals]


@router.get("/calendar/{cal_id}")
def get_calendar(cal_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(AcademicCalendar).filter(AcademicCalendar.id == cal_id).first()
    if not c:
        raise HTTPException(404, "Calendar not found")
    return _cal_dict(c)


@router.post("/calendar")
def create_calendar(
    p: CalendarIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    existing = db.query(AcademicCalendar).filter(
        AcademicCalendar.semester == p.semester, AcademicCalendar.year == p.year
    ).first()
    if existing:
        existing.sem_start = date.fromisoformat(p.sem_start)
        existing.sem_end = date.fromisoformat(p.sem_end)
        existing.label = p.label
        existing.working_days = p.working_days
        existing.updated_at = datetime.utcnow()
        db.commit()
        return {"message": "Calendar updated", "id": existing.id}

    cal = AcademicCalendar(
        semester=p.semester,
        sem_start=date.fromisoformat(p.sem_start),
        sem_end=date.fromisoformat(p.sem_end),
        year=p.year, label=p.label,
        working_days=p.working_days,
        created_by=user.username,
    )
    db.add(cal)
    db.commit()
    db.refresh(cal)
    return {"message": "Calendar created", "id": cal.id}


@router.delete("/calendar/{cal_id}")
def delete_calendar(
    cal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    c = db.query(AcademicCalendar).filter(AcademicCalendar.id == cal_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    db.delete(c)
    db.commit()
    return {"message": "Calendar deleted"}


@router.get("/calendar/working-dates/{cal_id}")
def get_working_dates(
    cal_id: int, subject: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cal = db.query(AcademicCalendar).filter(AcademicCalendar.id == cal_id).first()
    if not cal:
        raise HTTPException(404, "Calendar not found")
    dates = _compute_teaching_dates(db, cal, subject)
    return {"total": len(dates), "dates": [d.isoformat() for d in dates]}


def _cal_dict(c):
    wd = _compute_total_working_days(c)
    return {
        "id": c.id, "semester": c.semester, "year": c.year, "label": c.label,
        "sem_start": c.sem_start.isoformat(), "sem_end": c.sem_end.isoformat(),
        "working_days": c.working_days, "total_working_days": wd,
        "created_by": c.created_by,
        "created_at": c.created_at.isoformat() if c.created_at else "",
    }


def _compute_total_working_days(cal):
    day_map = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
    try:
        wd = json.loads(cal.working_days or '["MON","TUE","WED","THU","FRI","SAT"]')
    except Exception:
        wd = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
    allowed = {day_map[d] for d in wd if d in day_map}
    count = 0
    cur = cal.sem_start
    while cur <= cal.sem_end:
        if cur.weekday() in allowed:
            count += 1
        cur += timedelta(days=1)
    return count


def _compute_teaching_dates(db, cal, subject: str = "") -> List[date]:
    day_map = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
    try:
        wd = json.loads(cal.working_days or '["MON","TUE","WED","THU","FRI","SAT"]')
    except Exception:
        wd = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
    allowed_weekdays = {day_map[d] for d in wd if d in day_map}

    subject_days = set()
    if subject:
        slots = db.query(TimetableSlot).filter(
            TimetableSlot.subject == subject,
            TimetableSlot.semester == cal.semester,
        ).all()
        for s in slots:
            if s.day_name in day_map:
                subject_days.add(day_map[s.day_name])
    else:
        subject_days = allowed_weekdays

    holidays_q = db.query(HolidayLog).filter(
        HolidayLog.day >= cal.sem_start,
        HolidayLog.day <= cal.sem_end,
    ).all()
    holidays = set()
    for h in holidays_q:
        if h.subject is None or h.subject == subject:
            holidays.add(h.day)

    dates = []
    cur = cal.sem_start
    while cur <= cal.sem_end:
        if (
            cur.weekday() in subject_days
            and cur.weekday() in allowed_weekdays
            and cur not in holidays
        ):
            dates.append(cur)
        cur += timedelta(days=1)
    return dates


# ══════════════════════════════════════════════════════════
# 2. SYLLABUS — Upload, Extract with Gemini Vision, CRUD
# ══════════════════════════════════════════════════════════

@router.get("/syllabus")
def list_syllabi(
    semester: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Syllabus)
    if semester:
        q = q.filter(Syllabus.semester == semester)
    return [_syl_dict(s) for s in q.order_by(Syllabus.subject).all()]


@router.get("/syllabus/{syl_id}")
def get_syllabus(
    syl_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(Syllabus).filter(Syllabus.id == syl_id).first()
    if not s:
        raise HTTPException(404, "Syllabus not found")
    return _syl_dict(s)


@router.post("/syllabus/upload")
async def upload_syllabus(
    subject: str = Form(...),
    semester: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    """Faculty uploads image/PDF → Gemini extracts syllabus → Save."""
    content = await file.read()
    fname = file.filename or "syllabus"
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""

    # Save file
    safe_name = f"{subject.replace(' ', '_')}_sem{semester}_{int(datetime.utcnow().timestamp())}.{ext}"
    fpath = os.path.join(UPLOAD_DIR, safe_name)
    with open(fpath, "wb") as f:
        f.write(content)

    # Determine MIME type
    mime_map = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif",
        "webp": "image/webp", "pdf": "application/pdf",
    }
    mime = mime_map.get(ext)
    if not mime:
        raise HTTPException(400, f"Unsupported file type '.{ext}'. Upload a JPG, PNG, or PDF.")

    raw = ""
    if ext == "pdf":
        # For PDFs: extract text first, send as text to Gemini (more reliable & free)
        text_content = _extract_pdf_text(fpath)
        if text_content:
            prompt = f"""Extract the complete syllabus from the following text.
Return ONLY valid JSON in this exact format:
{{
  "subject": "Subject Name",
  "units": [
    {{
      "unit_number": 1,
      "title": "Unit Title",
      "topics": ["Topic 1", "Topic 2", "Topic 3"],
      "hours": 10
    }}
  ],
  "total_hours": 50
}}
Extract EVERY unit, EVERY topic. Return ONLY the JSON, no markdown, no backticks.

SYLLABUS TEXT:
{text_content[:15000]}"""
            raw = _call_gemini(prompt)
        else:
            # PDF text extraction failed — send as image
            b64 = base64.b64encode(content).decode("utf-8")
            raw = _call_gemini(_syllabus_extract_prompt(), b64, "application/pdf")
    else:
        # Image: send directly to Gemini Vision
        b64 = base64.b64encode(content).decode("utf-8")
        raw = _call_gemini(_syllabus_extract_prompt(), b64, mime)

    # Parse JSON response
    try:
        topics_data = json.loads(_clean_json(raw))
    except json.JSONDecodeError:
        topics_data = {"units": [], "raw_text": raw[:3000]}

    total_hours = topics_data.get(
        "total_hours",
        sum(u.get("hours", 0) for u in topics_data.get("units", []))
    )

    # Save or update
    existing = db.query(Syllabus).filter(
        Syllabus.subject == subject, Syllabus.semester == semester
    ).first()
    if existing:
        existing.raw_text = raw
        existing.topics_json = json.dumps(topics_data)
        existing.total_hours = total_hours
        existing.source_filename = safe_name
        existing.updated_at = datetime.utcnow()
        db.commit()
        return {"message": "Syllabus updated", "id": existing.id, "topics": topics_data}

    syl = Syllabus(
        subject=subject, semester=semester,
        raw_text=raw,
        topics_json=json.dumps(topics_data),
        total_hours=total_hours,
        source_filename=safe_name,
        uploaded_by=user.username,
    )
    db.add(syl)
    db.commit()
    db.refresh(syl)
    return {"message": "Syllabus extracted and saved", "id": syl.id, "topics": topics_data}


def _syllabus_extract_prompt() -> str:
    return """Extract the complete syllabus from this document. Return ONLY valid JSON:
{
  "subject": "Subject Name",
  "units": [
    {
      "unit_number": 1,
      "title": "Unit Title",
      "topics": ["Topic 1", "Topic 2", "Topic 3"],
      "hours": 10
    }
  ],
  "total_hours": 50
}
Extract EVERY unit, EVERY topic. Return ONLY the JSON, no markdown, no backticks."""


def _extract_pdf_text(fpath: str) -> str:
    """Extract text from PDF using pdfplumber (preferred) or PyPDF2 (fallback)."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(fpath) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        result = "\n".join(parts).strip()
        if result:
            print(f"[PDF] Extracted {len(result)} chars via pdfplumber")
            return result
    except ImportError:
        print("[PDF] pdfplumber not installed, trying PyPDF2")
    except Exception as e:
        print(f"[PDF pdfplumber error] {e}")

    try:
        import PyPDF2
        parts = []
        with open(fpath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        result = "\n".join(parts).strip()
        if result:
            print(f"[PDF] Extracted {len(result)} chars via PyPDF2")
            return result
    except ImportError:
        print("[PDF] PyPDF2 not installed either")
    except Exception as e:
        print(f"[PDF PyPDF2 error] {e}")

    return ""


@router.post("/syllabus/manual")
def add_syllabus_manual(
    subject: str = Form(...),
    semester: int = Form(...),
    topics_json: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    try:
        data = json.loads(topics_json)
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    total_hours = data.get("total_hours", sum(u.get("hours", 0) for u in data.get("units", [])))
    existing = db.query(Syllabus).filter(
        Syllabus.subject == subject, Syllabus.semester == semester
    ).first()
    if existing:
        existing.topics_json = topics_json
        existing.total_hours = total_hours
        existing.updated_at = datetime.utcnow()
        db.commit()
        return {"message": "Updated", "id": existing.id}

    syl = Syllabus(
        subject=subject, semester=semester,
        topics_json=topics_json, total_hours=total_hours,
        uploaded_by=user.username,
    )
    db.add(syl)
    db.commit()
    return {"message": "Saved", "id": syl.id}


@router.delete("/syllabus/{syl_id}")
def delete_syllabus(
    syl_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    s = db.query(Syllabus).filter(Syllabus.id == syl_id).first()
    if not s:
        raise HTTPException(404, "Not found")
    db.delete(s)
    db.commit()
    return {"message": "Deleted"}


def _syl_dict(s):
    try:
        topics = json.loads(s.topics_json) if s.topics_json else {}
    except Exception:
        topics = {}
    return {
        "id": s.id, "subject": s.subject, "semester": s.semester,
        "total_hours": s.total_hours, "source_filename": s.source_filename,
        "topics": topics, "uploaded_by": s.uploaded_by,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    }


# ══════════════════════════════════════════════════════════
# 3. LESSON PLAN — AI Generation with Gemini
# ══════════════════════════════════════════════════════════

@router.post("/lesson-plan/generate")
def generate_lesson_plan(
    subject: str = Form(...),
    semester: int = Form(...),
    calendar_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    syl = db.query(Syllabus).filter(
        Syllabus.subject == subject, Syllabus.semester == semester
    ).first()
    if not syl or not syl.topics_json:
        raise HTTPException(400, "Upload syllabus first for this subject")

    cal = db.query(AcademicCalendar).filter(AcademicCalendar.id == calendar_id).first()
    if not cal:
        raise HTTPException(400, "Academic calendar not found")

    teaching_dates = _compute_teaching_dates(db, cal, subject)
    if not teaching_dates:
        raise HTTPException(400, "No teaching dates found. Check timetable and calendar.")

    topics_data = json.loads(syl.topics_json)

    prompt = f"""You are an expert academic lesson planner. Create a detailed day-by-day lesson plan.

SYLLABUS:
{json.dumps(topics_data, indent=2)}

TEACHING DATES (total {len(teaching_dates)} classes available):
{json.dumps([d.isoformat() for d in teaching_dates])}

RULES:
1. Distribute ALL topics across the available dates
2. Cover EVERY topic before the semester ends
3. Include revision days before likely exam dates (last 5-7 classes)
4. Include 2-3 internal assessment/quiz days spread evenly
5. Group related topics together
6. Heavier topics get more days
7. Each day should have a clear, specific topic

Return ONLY valid JSON array (no markdown, no backticks):
[
  {{
    "date": "2026-01-15",
    "day_number": 1,
    "unit": "Unit 1",
    "topic": "Introduction to Machine Learning",
    "subtopics": "Definition, Types of ML, Applications",
    "teaching_method": "Lecture"
  }}
]

Cover ALL dates. teaching_method: Lecture, Lab, Discussion, Quiz, Internal Assessment, Revision, Project."""

    raw = _call_gemini(prompt)
    try:
        plan_data = json.loads(_clean_json(raw))
    except json.JSONDecodeError:
        raise HTTPException(502, f"AI returned invalid JSON. Raw: {raw[:300]}")

    # Archive old active plans
    for op in db.query(LessonPlan).filter(
        LessonPlan.subject == subject,
        LessonPlan.semester == semester,
        LessonPlan.status == "active",
    ).all():
        op.status = "archived"

    plan = LessonPlan(
        subject=subject, semester=semester,
        syllabus_id=syl.id, calendar_id=cal.id,
        total_classes=len(teaching_dates),
        plan_json=json.dumps(plan_data),
        generated_by=user.username,
    )
    db.add(plan)
    db.flush()

    for entry in plan_data:
        try:
            d = date.fromisoformat(entry["date"])
        except Exception:
            continue
        db.add(LessonPlanDay(
            plan_id=plan.id, day=d,
            day_number=entry.get("day_number", 0),
            unit=entry.get("unit", ""),
            topic=entry.get("topic", ""),
            subtopics=entry.get("subtopics", ""),
            teaching_method=entry.get("teaching_method", "Lecture"),
        ))

    db.commit()
    return {
        "message": f"Lesson plan generated! {len(plan_data)} classes planned.",
        "plan_id": plan.id,
        "classes": len(plan_data),
    }


@router.get("/lesson-plan")
def list_plans(
    subject: str = "", semester: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(LessonPlan).filter(LessonPlan.status == "active")
    if subject:
        q = q.filter(LessonPlan.subject == subject)
    if semester:
        q = q.filter(LessonPlan.semester == semester)
    return [_plan_dict(p) for p in q.order_by(LessonPlan.created_at.desc()).all()]


@router.get("/lesson-plan/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.query(LessonPlan).filter(LessonPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "Plan not found")
    return _plan_dict(p)


@router.get("/lesson-plan/{plan_id}/days")
def get_plan_days(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    days = db.query(LessonPlanDay).filter(
        LessonPlanDay.plan_id == plan_id
    ).order_by(LessonPlanDay.day).all()
    return [_day_dict(d) for d in days]


@router.put("/lesson-plan/day/{day_id}/status")
def update_day_status(
    day_id: int,
    status: str = Form(...),
    actual_topic: str = Form(""),
    remark: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    d = db.query(LessonPlanDay).filter(LessonPlanDay.id == day_id).first()
    if not d:
        raise HTTPException(404, "Day not found")
    d.status = status
    d.actual_topic = actual_topic or None
    d.remark = remark or None
    d.updated_at = datetime.utcnow()
    db.commit()
    return {"message": f"Day marked as {status}"}


@router.delete("/lesson-plan/{plan_id}")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    p = db.query(LessonPlan).filter(LessonPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "Not found")
    db.query(LessonPlanDay).filter(LessonPlanDay.plan_id == plan_id).delete()
    db.delete(p)
    db.commit()
    return {"message": "Plan deleted"}


# ══════════════════════════════════════════════════════════
# 4. AUTO-ADJUSTMENT
# ══════════════════════════════════════════════════════════

@router.post("/lesson-plan/{plan_id}/adjust")
def adjust_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    plan = db.query(LessonPlan).filter(LessonPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    cal = db.query(AcademicCalendar).filter(AcademicCalendar.id == plan.calendar_id).first()
    if not cal:
        raise HTTPException(400, "Calendar not found")

    all_days = db.query(LessonPlanDay).filter(
        LessonPlanDay.plan_id == plan_id
    ).order_by(LessonPlanDay.day).all()

    today     = date.today()
    completed = [d for d in all_days if d.status == "completed"]
    missed    = [d for d in all_days if d.status == "missed"]
    remaining = [d for d in all_days if d.status == "planned" and d.day >= today]

    missed_topics    = [{"topic": d.topic, "unit": d.unit, "subtopics": d.subtopics} for d in missed]
    planned_topics   = [{"date": d.day.isoformat(), "topic": d.topic, "unit": d.unit} for d in remaining]
    completed_topics = [d.topic for d in completed]

    if not missed_topics:
        return {"message": "No adjustment needed — no missed classes"}

    teaching_dates = _compute_teaching_dates(db, cal, plan.subject)
    future_dates   = [d for d in teaching_dates if d >= today]

    prompt = f"""You are an expert lesson plan adjuster. Faculty missed classes — reschedule remaining plan.

SUBJECT: {plan.subject}
COMPLETED (skip these): {json.dumps(completed_topics)}
MISSED (must cover): {json.dumps(missed_topics)}
PLANNED: {json.dumps(planned_topics)}
AVAILABLE DATES ({len(future_dates)} left): {json.dumps([d.isoformat() for d in future_dates])}

Return ONLY valid JSON array:
[{{"date":"2026-03-15","day_number":1,"unit":"Unit X","topic":"Topic","subtopics":"sub1,sub2","teaching_method":"Lecture"}}]"""

    raw = _call_gemini(prompt)
    try:
        new_plan = json.loads(_clean_json(raw))
    except Exception:
        raise HTTPException(502, "AI returned invalid JSON for adjustment")

    for d in remaining:
        db.delete(d)

    for entry in new_plan:
        try:
            d = date.fromisoformat(entry["date"])
        except Exception:
            continue
        db.add(LessonPlanDay(
            plan_id=plan_id, day=d,
            day_number=entry.get("day_number", 0),
            unit=entry.get("unit", ""),
            topic=entry.get("topic", ""),
            subtopics=entry.get("subtopics", ""),
            teaching_method=entry.get("teaching_method", "Lecture"),
        ))

    plan.adjustments_count = (plan.adjustments_count or 0) + 1
    plan.last_adjusted = datetime.utcnow()
    plan.plan_json = json.dumps(new_plan)
    db.commit()

    return {
        "message": f"Plan adjusted! {len(missed_topics)} missed topics into {len(new_plan)} classes.",
        "missed_count": len(missed_topics),
        "new_classes": len(new_plan),
        "adjustments": plan.adjustments_count,
    }


@router.post("/lesson-plan/{plan_id}/auto-sync")
def auto_sync_from_attendance(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "hod", "admin")),
):
    plan = db.query(LessonPlan).filter(LessonPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    today = date.today()
    days = db.query(LessonPlanDay).filter(
        LessonPlanDay.plan_id == plan_id,
        LessonPlanDay.day < today,
        LessonPlanDay.status == "planned",
    ).all()

    updated = 0
    for d in days:
        flog = db.query(FacultyLog).filter(
            FacultyLog.subject == plan.subject,
            FacultyLog.semester == plan.semester,
            FacultyLog.day == d.day,
        ).first()
        d.status = "completed" if (flog and flog.status == "completed") else "missed"
        d.updated_at = datetime.utcnow()
        updated += 1

    db.commit()
    return {"message": f"Synced {updated} days from attendance records", "updated": updated}


@router.get("/lesson-plan/{plan_id}/progress")
def plan_progress(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    days = db.query(LessonPlanDay).filter(LessonPlanDay.plan_id == plan_id).all()
    plan = db.query(LessonPlan).filter(LessonPlan.id == plan_id).first()
    total     = len(days)
    completed = sum(1 for d in days if d.status == "completed")
    missed    = sum(1 for d in days if d.status == "missed")
    planned   = sum(1 for d in days if d.status == "planned")
    today     = date.today()
    past_due  = sum(1 for d in days if d.status == "planned" and d.day < today)
    behind    = missed + past_due

    return {
        "plan_id": plan_id,
        "subject": plan.subject if plan else "",
        "total": total, "completed": completed, "missed": missed,
        "planned": planned, "past_due": past_due,
        "behind_schedule": behind,
        "progress_pct": round(completed / total * 100) if total else 0,
        "adjustments": plan.adjustments_count if plan else 0,
        "needs_adjustment": behind > 0,
    }


def _plan_dict(p):
    return {
        "id": p.id, "subject": p.subject, "semester": p.semester,
        "total_classes": p.total_classes, "status": p.status,
        "adjustments_count": p.adjustments_count,
        "generated_by": p.generated_by,
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "last_adjusted": p.last_adjusted.isoformat() if p.last_adjusted else None,
    }


def _day_dict(d):
    return {
        "id": d.id, "plan_id": d.plan_id, "day": d.day.isoformat(),
        "day_number": d.day_number, "unit": d.unit, "topic": d.topic,
        "subtopics": d.subtopics, "teaching_method": d.teaching_method,
        "status": d.status, "actual_topic": d.actual_topic, "remark": d.remark,
    }