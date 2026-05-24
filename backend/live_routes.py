"""
Live Routes — Real-time face recognition attendance (like reference track_images).
Flow:
  1. Faculty enters semester/subject → clicks "Take Attendance"
  2. Camera opens, scanning starts IMMEDIATELY
  3. Each recognized face is marked PRESENT in DB right away (real-time)
  4. MIN_SECONDS_BETWEEN_SAME_ID prevents duplicate marks
  5. Faculty clicks "Stop" → camera closes, summary shown
  6. HOD can view faculty's live feed via WebSocket
"""
import base64
import json
import time
from datetime import datetime, date
from typing import Optional, Set, Dict
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth import get_db, require_roles
from backend.models import User, LiveClassStatus, Student, Attendance, FacultyLog

router = APIRouter(tags=["Live"])

# ── Config (matching reference code) ─────────────────────
MIN_SECONDS_BETWEEN_SAME_ID = 30   # Don't re-mark same student within 30s
AUTO_STOP_MINUTES = 20              # Auto-stop attendance after 20 minutes

# ── In-memory state ──────────────────────────────────────
live_viewers: Set[WebSocket] = set()
attendance_active = False
attendance_data: Dict = {}
recognized_students: Dict[str, dict] = {}   # roll_no -> {name, time, count}
last_seen_time: Dict[str, float] = {}       # roll_no -> last detection timestamp

# AI model (loaded once)
_face_app = None
_embeddings = None
_ai_loaded = False

def _load_ai():
    global _face_app, _embeddings, _ai_loaded
    if _ai_loaded:
        return _face_app, _embeddings
    try:
        from ai_worker.face_manager import load_embeddings
        import insightface
        _face_app = insightface.app.FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
        _embeddings = load_embeddings()
        if _embeddings:
            _ai_loaded = True
            print(f"[AI] Loaded recognizer with {len(_embeddings)} students")
        else:
            print("[AI] No embeddings found — build embeddings first")
    except Exception as e:
        print(f"[AI] Face recognizer not available: {e}")
    return _face_app, _embeddings

class StartAttendanceIn(BaseModel):
    semester: int
    subject: str
    faculty_name: str = ""
    threshold: float = 0.4

# ── REST Endpoints ────────────────────────────────────────

@router.post("/live/start-attendance")
def start_attendance(
    payload: StartAttendanceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod")),
):
    """Start attendance session — like reference track_images().
    Camera opens on frontend, frames sent here for recognition.
    Each recognized face is marked PRESENT in DB immediately."""
    global attendance_active, attendance_data, recognized_students, last_seen_time

    face_app, embeddings = _load_ai()
    if not face_app or not embeddings:
        raise HTTPException(400,
            "AI model not ready. Register student faces and build embeddings first.")

    # Reset session state
    attendance_active = True
    attendance_data = {
        "semester": payload.semester,
        "subject": payload.subject,
        "faculty_name": payload.faculty_name or user.username,
        "threshold": payload.threshold,
        "started_at": time.time(),
    }
    recognized_students = {}
    last_seen_time = {}

    # Update live class status for HOD monitoring
    live = db.query(LiveClassStatus).first()
    if not live:
        live = LiveClassStatus()
        db.add(live)
    live.is_active = True
    live.camera_streaming = True
    live.attendance_running = True
    live.faculty_name = payload.faculty_name or user.username
    live.subject = payload.subject
    live.semester = payload.semester
    live.started_at = datetime.now()
    live.present_count = 0
    db.commit()

    return {
        "message": f"Attendance started for {payload.subject} (Sem {payload.semester})",
        "subject": payload.subject,
        "semester": payload.semester,
    }

@router.post("/live/process-frame")
async def process_frame(
    frame: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod")),
):
    """Process webcam frame — detect faces, recognize, MARK ATTENDANCE IMMEDIATELY.
    Like reference code: recognized face → instantly marked present in DB."""

    # Broadcast frame to HOD live viewers
    await _broadcast_frame(frame)

    if not attendance_active:
        return {"faces": [], "recognized_count": 0, "attendance_active": False,
                "newly_marked": []}

    face_app, embeddings = _load_ai()
    if not face_app or not embeddings:
        return {"faces": [], "recognized_count": len(recognized_students),
                "attendance_active": True, "newly_marked": []}

    try:
        import cv2
        import numpy as np
        from ai_worker.config import MATCH_THRESHOLD

        threshold = attendance_data.get("threshold", MATCH_THRESHOLD)
        semester = attendance_data.get("semester", 8)
        subject = attendance_data.get("subject", "")
        faculty_name = attendance_data.get("faculty_name", "AI")
        now = time.time()
        today = date.today()

        # Decode frame
        frame_data = frame.split(",")[-1] if "," in frame else frame
        img_bytes = base64.b64decode(frame_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"faces": [], "recognized_count": len(recognized_students),
                    "attendance_active": True, "newly_marked": []}

        faces = face_app.get(img)
        frame_results = []
        newly_marked = []

        for face in faces:
            emb = face.embedding
            emb = emb / np.linalg.norm(emb)
            best_match = None
            best_score = 0

            for roll_no, stored_embs in embeddings.items():
                for se in stored_embs:
                    se_norm = se / np.linalg.norm(se)
                    score = float(np.dot(emb, se_norm))
                    if score > best_score:
                        best_score = score
                        best_match = roll_no

            bbox = face.bbox.astype(int).tolist()

            if best_match and best_score >= threshold:
                # ── MARK ATTENDANCE IMMEDIATELY (like reference code) ──
                # Check MIN_SECONDS_BETWEEN_SAME_ID to prevent spam
                last_time = last_seen_time.get(best_match, 0)
                is_new = best_match not in recognized_students

                if now - last_time >= MIN_SECONDS_BETWEEN_SAME_ID or is_new:
                    last_seen_time[best_match] = now

                    # Get student name
                    student = db.query(Student).filter(
                        Student.roll_no == best_match).first()
                    student_name = student.name if student else best_match

                    # Skip if student is from different semester
                    if student and student.semester != semester:
                        frame_results.append({
                            "roll_no": best_match, "score": round(best_score, 2),
                            "bbox": bbox, "known": True,
                            "name": f"{student_name} (Sem {student.semester})",
                            "wrong_sem": True,
                        })
                        continue

                    if is_new:
                        # First time seeing this student — mark present in DB
                        recognized_students[best_match] = {
                            "name": student_name,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "score": round(best_score, 2),
                            "count": 1,
                        }

                        # Save to database IMMEDIATELY
                        existing = db.query(Attendance).filter(
                            Attendance.roll_no == best_match,
                            Attendance.subject == subject,
                            Attendance.day == today
                        ).first()

                        if existing:
                            existing.status = "P"
                            existing.marked_by = f"AI ({faculty_name})"
                        else:
                            db.add(Attendance(
                                roll_no=best_match, name=student_name,
                                semester=semester, subject=subject,
                                day=today, status="P",
                                marked_by=f"AI ({faculty_name})",
                            ))
                        db.commit()

                        newly_marked.append({
                            "roll_no": best_match,
                            "name": student_name,
                            "score": round(best_score, 2),
                        })
                        print(f"[ATTENDANCE] ✅ Marked PRESENT: {best_match} ({student_name}) — score {best_score:.2f}")
                    else:
                        # Already marked, just update count
                        recognized_students[best_match]["count"] += 1

                frame_results.append({
                    "roll_no": best_match, "score": round(best_score, 2),
                    "bbox": bbox, "known": True,
                    "name": recognized_students.get(best_match, {}).get("name", best_match),
                })
            else:
                frame_results.append({
                    "roll_no": "Unknown", "score": round(best_score, 2),
                    "bbox": bbox, "known": False, "name": "Unknown",
                })

        # Update live status for HOD
        live = db.query(LiveClassStatus).first()
        if live:
            live.present_count = len(recognized_students)
            db.commit()

        # Broadcast detections to HOD viewers
        detection_msg = json.dumps({
            "type": "detections", "faces": frame_results,
            "recognized_count": len(recognized_students),
            "newly_marked": newly_marked,
        })
        for viewer in list(live_viewers):
            try:
                await viewer.send_text(detection_msg)
            except:
                live_viewers.discard(viewer)

        elapsed = int(now - attendance_data.get("started_at", now))

        # Auto-stop after 20 minutes
        auto_stopped = False
        if elapsed >= AUTO_STOP_MINUTES * 60:
            auto_stopped = True

        return {
            "faces": frame_results,
            "recognized_count": len(recognized_students),
            "attendance_active": True,
            "newly_marked": newly_marked,
            "elapsed": elapsed,
            "auto_stopped": auto_stopped,
        }

    except Exception as e:
        print(f"[AI-PROCESS-ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"faces": [], "recognized_count": len(recognized_students),
                "attendance_active": True, "newly_marked": [],
                "error": str(e)}

@router.post("/live/stop-attendance")
def stop_attendance(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "faculty", "hod")),
):
    """Stop attendance session. Attendance already saved in real-time.
    Now mark remaining students as ABSENT and update Excel."""
    global attendance_active

    if not attendance_active:
        return {"message": "No attendance session running",
                "present_count": 0, "absent_count": 0, "total": 0}

    attendance_active = False
    semester = attendance_data.get("semester", 8)
    subject = attendance_data.get("subject", "")
    faculty_name = attendance_data.get("faculty_name", "AI")
    today = date.today()

    # Get all students in this semester
    students = db.query(Student).filter(Student.semester == semester).all()
    present_rolls = set(recognized_students.keys())

    # Mark ABSENT for students NOT recognized
    for st in students:
        roll = str(st.roll_no)
        if roll not in present_rolls:
            existing = db.query(Attendance).filter(
                Attendance.roll_no == roll,
                Attendance.subject == subject,
                Attendance.day == today
            ).first()
            if existing:
                existing.status = "A"
                existing.marked_by = f"AI ({faculty_name})"
            else:
                db.add(Attendance(
                    roll_no=roll, name=st.name, semester=semester,
                    subject=subject, day=today, status="A",
                    marked_by=f"AI ({faculty_name})",
                ))
    db.commit()

    # Update Excel register
    statuses = {}
    for st in students:
        roll = str(st.roll_no)
        statuses[roll] = "P" if roll in present_rolls else "A"

    try:
        from backend.excel_register import update_subject_excel
        update_subject_excel(
            semester=semester, subject=subject,
            students=[{"roll_no": s.roll_no, "name": s.name} for s in students],
            day=today, statuses=statuses,
        )
        print(f"[EXCEL] Updated register for {subject}")
    except Exception as e:
        print(f"[EXCEL-ERROR] {e}")

    # Send notifications
    for st in students:
        roll = str(st.roll_no)
        total = db.query(Attendance).filter(
            Attendance.roll_no == roll, Attendance.subject == subject).count()
        present_c = db.query(Attendance).filter(
            Attendance.roll_no == roll, Attendance.subject == subject,
            Attendance.status == "P").count()
        avg = round((present_c / total * 100), 1) if total > 0 else 0
        try:
            from backend.notification import notify_attendance
            notify_attendance(
                student_name=st.name, roll_no=roll, subject=subject,
                date_str=today.isoformat(), status=statuses[roll],
                email=st.email, phone=st.phone, average=avg,
            )
        except Exception as e:
            pass

    # Update live status
    live = db.query(LiveClassStatus).first()
    if live:
        live.is_active = False
        live.camera_streaming = False
        live.attendance_running = False
        live.present_count = len(present_rolls)
        db.commit()

    # Log faculty activity
    try:
        elapsed = int(time.time() - attendance_data.get("started_at", time.time()))
        fl = FacultyLog(
            faculty_username=faculty_name,
            subject=subject, semester=semester,
            day=today,
            actual_start=datetime.fromtimestamp(attendance_data.get("started_at", time.time())),
            actual_end=datetime.now(),
            duration_minutes=elapsed // 60,
            present_count=len(present_rolls),
            absent_count=len(students) - len(present_rolls),
            total_count=len(students),
            mode=attendance_data.get("mode", "manual"),
            status="completed",
        )
        # Try to find scheduled slot
        days_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        from backend.models import TimetableSlot
        slot = db.query(TimetableSlot).filter(
            TimetableSlot.day_name == days_map.get(today.weekday(), ""),
            TimetableSlot.subject == subject,
            TimetableSlot.faculty_username == faculty_name,
        ).first()
        if slot:
            fl.scheduled_start = slot.start_time
            fl.scheduled_end = slot.end_time
        db.add(fl)
        db.commit()
    except Exception as e:
        print(f"[FACULTY-LOG-ERROR] {e}")

    # Build summary like reference code
    present_list = []
    for roll, info in recognized_students.items():
        present_list.append({
            "roll_no": roll,
            "name": info["name"],
            "time": info["time"],
            "score": info["score"],
        })

    elapsed = int(time.time() - attendance_data.get("started_at", time.time()))
    mins = elapsed // 60
    secs = elapsed % 60

    return {
        "message": f"Attendance complete! {len(present_rolls)} present, {len(students) - len(present_rolls)} absent",
        "present_count": len(present_rolls),
        "absent_count": len(students) - len(present_rolls),
        "total": len(students),
        "subject": subject,
        "semester": semester,
        "duration": f"{mins}m {secs}s",
        "present": present_list,
    }

@router.get("/live/status")
def live_status(db: Session = Depends(get_db)):
    live = db.query(LiveClassStatus).first()
    if not live or not live.is_active:
        return {"is_active": False, "camera_streaming": False,
                "attendance_running": attendance_active}
    return {
        "is_active": live.is_active,
        "faculty_name": live.faculty_name,
        "subject": live.subject,
        "semester": live.semester,
        "started_at": live.started_at.isoformat() if live.started_at else None,
        "present_count": live.present_count,
        "camera_streaming": live.camera_streaming,
        "attendance_running": attendance_active,
        "recognized_count": len(recognized_students),
    }

@router.get("/live/attendance-progress")
def attendance_progress(db: Session = Depends(get_db)):
    if not attendance_active:
        return {"active": False, "recognized": [], "count": 0}

    elapsed = int(time.time() - attendance_data.get("started_at", time.time()))
    recognized_list = [
        {"roll_no": roll, "name": info["name"], "time": info["time"],
         "score": info["score"]}
        for roll, info in recognized_students.items()
    ]

    return {
        "active": True, "elapsed": elapsed,
        "recognized": recognized_list,
        "count": len(recognized_students),
        "subject": attendance_data.get("subject", ""),
        "semester": attendance_data.get("semester", 0),
    }

@router.post("/live/reload-embeddings")
def reload_embeddings(user: User = Depends(require_roles("admin", "faculty", "hod"))):
    global _face_app, _embeddings, _ai_loaded
    _ai_loaded = False
    face_app, embeddings = _load_ai()
    if embeddings:
        return {"message": f"Reloaded! {len(embeddings)} students in model"}
    else:
        return {"message": "No embeddings found. Build embeddings first."}

@router.get("/live/test-ai")
def test_ai():
    """Test if AI model and embeddings load correctly."""
    import importlib
    errors = []

    # Check insightface
    try:
        import insightface
    except ImportError:
        errors.append("insightface not installed. Run: pip install insightface-0_7_3-cp311-cp311-win_amd64.whl")

    # Check onnxruntime
    try:
        import onnxruntime
    except ImportError:
        errors.append("onnxruntime not installed. Run: pip install onnxruntime")

    # Check opencv
    try:
        import cv2
    except ImportError:
        errors.append("opencv not installed. Run: pip install opencv-python")

    # Check embeddings file
    from ai_worker.config import EMBEDDINGS_FILE, KNOWN_FACES_DIR
    emb_exists = EMBEDDINGS_FILE.exists()
    if not emb_exists:
        errors.append(f"No embeddings.npz file found at {EMBEDDINGS_FILE}. Register faces and build embeddings first.")

    # Check known_faces
    students_with_faces = 0
    if KNOWN_FACES_DIR.exists():
        for d in KNOWN_FACES_DIR.iterdir():
            if d.is_dir() and list(d.glob("*.jpg")):
                students_with_faces += 1

    # Try loading
    face_app, embeddings = _load_ai()
    emb_count = len(embeddings) if embeddings else 0

    if errors:
        return {"ok": False, "errors": errors, "students_with_faces": students_with_faces,
                "embeddings_loaded": emb_count}

    return {"ok": True, "message": f"AI ready! {emb_count} students in model, {students_with_faces} with face photos",
            "students_with_faces": students_with_faces, "embeddings_loaded": emb_count}

# ── Surveillance Mode (HOD/Principal) ─────────────────────

@router.post("/live/surveillance-frame")
async def surveillance_frame(
    frame: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "principal")),
):
    """Process frame for surveillance — face detection only, no attendance marking."""
    # Broadcast to all live viewers
    await _broadcast_frame(frame)

    face_app, embeddings = _load_ai()
    if not face_app:
        return {"faces": [], "person_count": 0}

    try:
        import cv2, numpy as np, base64
        frame_data = frame.split(",")[-1] if "," in frame else frame
        img_bytes = base64.b64decode(frame_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"faces": [], "person_count": 0}

        faces = face_app.get(img)
        results = []
        for face in faces:
            bbox = face.bbox.astype(int).tolist()
            name = "Unknown"
            score = 0
            known = False
            if embeddings:
                emb = face.embedding
                emb = emb / np.linalg.norm(emb)
                for roll_no, stored_embs in embeddings.items():
                    for se in stored_embs:
                        se_norm = se / np.linalg.norm(se)
                        s = float(np.dot(emb, se_norm))
                        if s > score:
                            score = s
                            best = roll_no
                if score >= 0.4:
                    st = db.query(Student).filter(Student.roll_no == best).first()
                    name = st.name if st else best
                    known = True
            results.append({"bbox": bbox, "name": name, "score": round(score, 2), "known": known})

        # Broadcast detections
        import json
        msg = json.dumps({"type": "detections", "faces": results, "person_count": len(faces)})
        for viewer in list(live_viewers):
            try:
                await viewer.send_text(msg)
            except:
                live_viewers.discard(viewer)

        return {"faces": results, "person_count": len(faces)}
    except Exception as e:
        return {"faces": [], "person_count": 0, "error": str(e)}

# ── WebSocket broadcast to HOD live viewers ───────────────

async def _broadcast_frame(frame_b64: str):
    global live_viewers
    if not live_viewers:
        return
    msg = json.dumps({"type": "frame", "data": frame_b64})
    dead = set()
    for viewer in live_viewers:
        try:
            await viewer.send_text(msg)
        except:
            dead.add(viewer)
    live_viewers -= dead

@router.websocket("/ws/live-view")
async def live_view_ws(websocket: WebSocket):
    await websocket.accept()
    live_viewers.add(websocket)
    print(f"[WS] HOD viewer connected (total: {len(live_viewers)})")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        live_viewers.discard(websocket)
        print(f"[WS] HOD viewer disconnected (total: {len(live_viewers)})")


