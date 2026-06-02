# AI-ML PDA Attendance System

An AI-powered Face Recognition Attendance Management System developed using FastAPI, InsightFace, OpenCV, and SQLite. The platform automates student attendance using real-time facial recognition and provides intelligent dashboards for faculty and HOD management.
https://youtu.be/HfhYhcG8UjE -----> DEMO VIDEO
---

# Features

- Real-time Face Recognition Attendance
- AI-based Student Identification
- Automatic Attendance Logging
- HOD & Faculty Dashboards
- Semester-wise Student Management
- Attendance Reports & Analytics
- Excel Export Support
- Webcam-based Student Registration
- Face Embedding Generation
- Timetable & Alerts System
- InsightFace + ONNX Runtime Integration

---

# Tech Stack

## Backend
- Python
- FastAPI
- SQLAlchemy
- SQLite

## AI / Computer Vision
- InsightFace
- OpenCV
- ONNX Runtime
- NumPy

## Frontend
- HTML
- CSS
- JavaScript

---

# System Workflow

```text
Student Registration
        ↓
Face Image Capture
        ↓
Face Embedding Generation
        ↓
Real-Time Face Detection
        ↓
Student Recognition
        ↓
Attendance Verification
        ↓
Attendance Stored in Database
        ↓
Dashboard & Report Generation
```

---

# Project Structure

```text
AI-ML-PDA-ATTENDENCE-SYSTEM/
│
├── ai_worker/              # AI recognition and embedding modules
├── backend/                # FastAPI backend services
├── frontend/               # Frontend dashboard and UI
├── requirements.txt        # Python dependencies
├── setup_users.py          # Default user setup
├── attendance.db           # SQLite database
├── start_server.bat        # Server start script
├── stop_server.bat         # Server stop script
└── README.md
```

---

# AI Models Used

The system uses advanced face recognition models for high-accuracy attendance automation.

## Technologies Used
- InsightFace Buffalo_L Model
- ONNX Runtime Inference Engine
- Face Embedding Recognition Pipeline

---

# Installation Guide

## 1. Clone Repository

```bash
git clone https://github.com/sunandamanne616-droid/AI-ML-PDA-ATTENDENCE-SYSTEM.git
cd AI-ML-PDA-ATTENDENCE-SYSTEM
```

---

## 2. Create Virtual Environment

```bash
python -m venv venv
```

---

## 3. Activate Environment

### Mac/Linux
```bash
source venv/bin/activate
```

### Windows
```bash
venv\Scripts\activate
```

---

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

If needed:

```bash
pip install insightface onnxruntime python-dotenv
```

---

## 5. Run Server

```bash
python -m uvicorn backend.main:app --reload --port 8002
```

---

## 6. Open in Browser

```text
http://localhost:8002/dashboard
```

---

# Default Login Credentials

| Role | Username | Password |
|---|---|---|
| HOD | hod1 | hod123 |
| Faculty | faculty1 | faculty123 |

---

# Face Registration Workflow

1. Open Face Recognition Panel
2. Enter Student Roll Number
3. Capture Face Images
4. Generate Face Embeddings
5. Start Attendance Recognition

---

# Current Functionalities

- Student Registration
- Face Embedding Generation
- Live Face Recognition
- Automated Attendance Tracking
- Dashboard Monitoring
- Excel Report Generation
- Faculty & HOD Access Panels

---

# Screenshots

Add screenshots here:

```text
/screenshots/dashboard.png
/screenshots/recognition.png
/screenshots/attendance_logs.png
/screenshots/admin_panel.png
```

---

# Future Improvements

- Cloud Database Integration
- Multi-Camera Support
- Mobile App Integration
- Advanced Analytics Dashboard
- Real-Time Notifications
- GPU Acceleration
- Anti-Spoofing Security
- Docker Deployment
- Role-Based Authentication

---

# Performance Goals

- High-accuracy face recognition
- Low-latency attendance processing
- Real-time webcam inference
- Scalable attendance management architecture

---

# Developer

## Sunanda Manne
Artificial Intelligence & Machine Learning Engineer

- GitHub: https://github.com/sunandamanne616-droid

---

# License

This project is developed for academic, research, and educational purposes.
This project is developed for academic and research purposes.
<<img width="690" height="319" alt="Screenshot 2026-05-24 at 1 17 10 PM" src="https://github.com/user-attachments/assets/3c7972b0-aae2-4ff7-8614-7be46797db58" />
<img width="1470" height="795" alt="Screenshot 2026-05-24 at 1 17 04 PM" src="https://github.com/user-attachments/assets/058e2e70-b35e-4d01-814f-2b47c45fa29e" />
<img width="703" height="638" alt="Screenshot 2026-05-24 at 1 16 50 PM" src="https://github.com/user-attachments/assets/a8666173-99bc-41e6-8b99-379369d6251e" />
<img width="884" height="803" alt="Screenshot 2026-05-24 at 1 17 42 PM" src="https://github.com/user-attachments/assets/01acf05e-d554-414c-a543-121336354a71" />
<img width="637" height="786" alt="Screenshot 2026-05-24 at 1 17 16 PM" src="https://github.com/user-attachments/assets/6c5b67a2-2a58-4192-9316-27c555219893" />
<img width="516" height="798" alt="Screenshot 2026-05-24 at 1 17 31 PM" src="https://github.com/user-attachments/assets/14d0eca8-418f-49c3-8e8d-53576ceda1ec" />
<img width="1124" height="793" alt="Screenshot 2026-05-24 at 1 17 26 PM" src="https://github.com/user-attachments/assets/1e033b36-9924-4f11-a17d-11df58c5c88f" />

