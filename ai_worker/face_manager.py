"""Face manager — handles face registration, embedding building, and loading."""
import os
import shutil
import cv2
import numpy as np
from typing import Dict, List, Optional
from ai_worker.config import KNOWN_FACES_DIR, EMBEDDINGS_FILE, MODEL_NAME

_face_app = None


def _get_face_app():
    global _face_app
    if _face_app is None:
        import insightface
        _face_app = insightface.app.FaceAnalysis(name=MODEL_NAME, providers=["CPUExecutionProvider"])
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
    return _face_app


def register_from_bytes(roll_no: str, img_bytes: bytes) -> bool:
    """Register a face from raw image bytes (e.g. webcam frame)."""
    app = _get_face_app()
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return False

    faces = app.get(img)
    if len(faces) != 1:
        return False  # Need exactly one face

    student_dir = KNOWN_FACES_DIR / roll_no
    student_dir.mkdir(parents=True, exist_ok=True)

    existing = len(list(student_dir.glob("face_*.jpg")))
    face = faces[0]

    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = max(0, bbox[0]), max(0, bbox[1]), bbox[2], bbox[3]
    cropped = img[y1:y2, x1:x2]
    if cropped.size > 0:
        cv2.imwrite(str(student_dir / f"face_{existing}.jpg"), cropped)

    cv2.imwrite(str(student_dir / f"full_{existing}.jpg"), img)
    return True


def register_from_image(roll_no: str, image_path: str) -> bool:
    app = _get_face_app()
    img = cv2.imread(image_path)
    if img is None:
        return False

    faces = app.get(img)
    if not faces:
        return False

    student_dir = KNOWN_FACES_DIR / roll_no
    student_dir.mkdir(parents=True, exist_ok=True)

    existing = len(list(student_dir.glob("face_*.jpg")))
    face = faces[0]

    # Save cropped face
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = max(0, bbox[0]), max(0, bbox[1]), bbox[2], bbox[3]
    cropped = img[y1:y2, x1:x2]
    if cropped.size > 0:
        cv2.imwrite(str(student_dir / f"face_{existing}.jpg"), cropped)

    # Save full image
    cv2.imwrite(str(student_dir / f"full_{existing}.jpg"), img)
    return True


def build_embeddings() -> Dict[str, List[np.ndarray]]:
    app = _get_face_app()
    KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)

    all_embeddings = {}

    for student_dir in sorted(KNOWN_FACES_DIR.iterdir()):
        if not student_dir.is_dir():
            continue
        roll_no = student_dir.name
        embs = []

        for img_file in sorted(student_dir.glob("*.jpg")):
            img = cv2.imread(str(img_file))
            if img is None:
                continue
            faces = app.get(img)
            if faces:
                embs.append(faces[0].embedding)

        if embs:
            all_embeddings[roll_no] = embs
            print(f"  ✅ {roll_no}: {len(embs)} embedding(s)")

    # Save
    save_data = {}
    for roll_no, embs in all_embeddings.items():
        save_data[roll_no] = np.array(embs)

    np.savez(str(EMBEDDINGS_FILE), **save_data)
    print(f"💾 Saved embeddings for {len(all_embeddings)} students")
    return all_embeddings


def build_single_embedding(roll_no: str) -> bool:
    """Build embedding for ONE student only, merge into existing file."""
    app = _get_face_app()
    student_dir = KNOWN_FACES_DIR / roll_no
    if not student_dir.exists():
        return False

    embs = []
    for img_file in sorted(student_dir.glob("*.jpg")):
        img = cv2.imread(str(img_file))
        if img is None:
            continue
        faces = app.get(img)
        if faces:
            embs.append(faces[0].embedding)

    if not embs:
        return False

    # Load existing embeddings and add/replace this student
    existing = {}
    if EMBEDDINGS_FILE.exists():
        data = np.load(str(EMBEDDINGS_FILE), allow_pickle=True)
        for key in data.files:
            existing[key] = data[key]

    existing[roll_no] = np.array(embs)
    np.savez(str(EMBEDDINGS_FILE), **existing)
    print(f"  ✅ {roll_no}: {len(embs)} embedding(s) (quick build)")
    return True


def load_embeddings() -> Optional[Dict[str, List[np.ndarray]]]:
    if not EMBEDDINGS_FILE.exists():
        return None
    data = np.load(str(EMBEDDINGS_FILE), allow_pickle=True)
    result = {}
    for roll_no in data.files:
        arr = data[roll_no]
        if arr.ndim == 1:
            result[roll_no] = [arr]
        else:
            result[roll_no] = [arr[i] for i in range(arr.shape[0])]
    return result


def list_registered_students() -> List[dict]:
    KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for d in sorted(KNOWN_FACES_DIR.iterdir()):
        if d.is_dir():
            photos = len(list(d.glob("*.jpg")))
            result.append({"roll_no": d.name, "photos": photos})
    return result


def delete_student_faces(roll_no: str) -> bool:
    student_dir = KNOWN_FACES_DIR / roll_no
    if student_dir.exists():
        shutil.rmtree(student_dir)
        return True
    return False
