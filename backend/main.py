from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import os

from backend.database import Base, engine
from backend.auth import get_db, hash_password, verify_password, create_access_token, get_current_user
from backend.models import User

from backend.users import router as students_router
from backend.attendance import router as attendance_router
from backend.timetable import router as timetable_router
from backend.excel_routes import router as excel_router
from backend.live_routes import router as live_router
from backend.face_routes import router as face_router
from backend.academic_planner import router as planner_router
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="AIML Attendance & Live Monitoring System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# ── Startup: launch background scheduler ──────────────────
@app.on_event("startup")
async def on_startup():
    try:
        from backend.scheduler import start_scheduler
        await start_scheduler()
    except Exception as e:
        print(f"[SCHEDULER] Could not start: {e}")

@app.get("/")
def root():
    return {"message": "Backend running", "dashboard": "/dashboard", "docs": "/docs"}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/register")
def register(username: str, password: str, role: str, email: str = "",
             db: Session = Depends(get_db)):
    username = username.strip()
    role = role.strip().lower()
    if role not in ("admin", "faculty", "hod", "student", "principal"):
        raise HTTPException(status_code=400, detail="Invalid role")
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    u = User(username=username, hashed_password=hash_password(password),
             role=role, email=email.strip() if email else None)
    db.add(u)
    db.commit()
    return {"message": "user created", "username": username, "role": role}

@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(username=user.username, role=user.role)
    return {"access_token": token, "token_type": "bearer",
            "role": user.role, "username": user.username}

@app.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username, "role": user.role, "email": user.email}

@app.get("/alerts")
def get_alerts(db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    from backend.models import AlertLog
    alerts = db.query(AlertLog).order_by(AlertLog.created_at.desc()).limit(20).all()
    return [{"id": a.id, "type": a.alert_type, "message": a.message,
             "time": a.created_at.isoformat(), "resolved": a.resolved} for a in alerts]

# ── Dashboard ─────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse, tags=["Frontend"])
def dashboard():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "frontend", "dashboard.html")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Put dashboard.html inside frontend/ folder</h1>")

# ── Routers ───────────────────────────────────────────────
app.include_router(students_router)
app.include_router(attendance_router)
app.include_router(timetable_router)
app.include_router(excel_router)
app.include_router(live_router)
app.include_router(face_router)
app.include_router(planner_router)

