"""Face Recognition API Routes — register faces, build embeddings, manage face data."""
import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from backend.auth import get_db, require_roles
from backend.models import User, Student

router = APIRouter(prefix="/face", tags=["Face Recognition"])

@router.post("/register-frame")
async def register_face_frame(
    roll_no: str = Form(...),
    frame: str = Form(...),  # base64 JPEG data
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty")),
):
    """Register a face from a webcam frame (base64 encoded)."""
    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(404, f"Student {roll_no} not found")

    import base64
    try:
        # Strip data URL prefix if present
        if "," in frame:
            frame = frame.split(",", 1)[1]
        img_bytes = base64.b64decode(frame)
    except Exception:
        raise HTTPException(400, "Invalid base64 image data")

    try:
        from ai_worker.face_manager import register_from_bytes
        success = register_from_bytes(roll_no, img_bytes)
    except ImportError:
        raise HTTPException(500, "ai_worker not found")
    except Exception as e:
        raise HTTPException(500, f"Face registration error: {str(e)}")

    if success:
        return {"message": "Frame captured", "roll_no": roll_no}
    else:
        return {"message": "No single face detected in frame", "roll_no": roll_no, "skipped": True}

@router.post("/register-image")
async def register_face_image(
    roll_no: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hod", "faculty")),
):
    student = db.query(Student).filter(Student.roll_no == roll_no).first()
    if not student:
        raise HTTPException(404, f"Student {roll_no} not found")

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file")

    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        from ai_worker.face_manager import register_from_image
        success = register_from_image(roll_no, tmp_path)
    except ImportError:
        raise HTTPException(500, "ai_worker not found. Make sure ai_worker/ folder exists and insightface is installed.")
    except Exception as e:
        raise HTTPException(500, f"Face registration error: {str(e)}")
    finally:
        os.unlink(tmp_path)

    if success:
        return {"message": f"Face registered for {roll_no} ({student.name})",
                "roll_no": roll_no, "name": student.name}
    else:
        raise HTTPException(400, "No face detected in the uploaded image.")

@router.post("/build-single/{roll_no}")
def build_single(roll_no: str, user: User = Depends(require_roles("admin", "faculty", "hod"))):
    try:
        from ai_worker.face_manager import build_single_embedding
        ok = build_single_embedding(roll_no)
        if ok:
            return {"message": f"Embeddings built for {roll_no}"}
        raise HTTPException(400, f"No faces found for {roll_no}")
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/build-embeddings")
def build_embeddings_route(user: User = Depends(require_roles("admin", "hod", "faculty"))):
    try:
        from ai_worker.face_manager import build_embeddings, list_registered_students
        students = list_registered_students()
        if not students:
            raise HTTPException(404, "No faces registered yet.")
        embeddings = build_embeddings()
        return {"message": f"Embeddings built for {len(embeddings)} students",
                "students": list(embeddings.keys())}
    except ImportError:
        raise HTTPException(500, "ai_worker not found")
    except Exception as e:
        raise HTTPException(500, f"Build error: {str(e)}")

@router.get("/registered")
def list_registered(user: User = Depends(require_roles("admin", "hod", "faculty"))):
    try:
        from ai_worker.face_manager import list_registered_students
        students = list_registered_students()
        return {"count": len(students), "students": students}
    except ImportError:
        return {"count": 0, "students": [], "warning": "ai_worker not installed"}

@router.delete("/{roll_no}")
def delete_face_data(roll_no: str, user: User = Depends(require_roles("admin", "hod"))):
    try:
        from ai_worker.face_manager import delete_student_faces
        if delete_student_faces(roll_no):
            return {"message": f"Face data deleted for {roll_no}"}
        else:
            raise HTTPException(404, f"No face data found for {roll_no}")
    except ImportError:
        raise HTTPException(500, "ai_worker not found")


