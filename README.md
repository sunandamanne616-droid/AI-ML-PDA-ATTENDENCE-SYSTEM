AI-ML-PDA-ATTENDENCE-SYSTEM

An AI-powered Face Recognition Attendance Management System developed using FastAPI, InsightFace, OpenCV, HTML/CSS/JavaScript, and SQLite.
This system automates student attendance using real-time face recognition and provides dashboards for faculty and HOD management.

Features
Real-time Face Recognition Attendance
AI-based Student Identification
Automatic Attendance Logging
HOD & Faculty Dashboards
Semester-wise Student Management
Attendance Reports
Excel Export Support
Face Embedding Generation
Webcam-based Registration
InsightFace + ONNX Runtime Integration
Timetable & Alerts System
Tech Stack
Backend
Python
FastAPI
SQLAlchemy
SQLite
AI / Computer Vision
InsightFace
OpenCV
ONNX Runtime
NumPy
Frontend
HTML
CSS
JavaScript
Project Structure
AI-ML-PDA-ATTENDENCE-SYSTEM/
│
├── ai_worker/
├── backend/
├── frontend/
├── requirements.txt
├── setup_users.py
├── attendance.db
└── README.md
Installation
1. Clone Repository
git clone https://github.com/sunandamanne616-droid/AI-ML-PDA-ATTENDENCE-SYSTEM.git
cd AI-ML-PDA-ATTENDENCE-SYSTEM
2. Create Virtual Environment
python -m venv venv

Activate Environment:

Mac/Linux
source venv/bin/activate
Windows
venv\Scripts\activate
3. Install Dependencies
pip install -r requirements.txt

If needed:

pip install insightface onnxruntime python-dotenv
4. Run Server
python -m uvicorn backend.main:app --reload --port 8002
5. Open in Browser
http://localhost:8002/dashboard
Default Login Credentials
Role	Username	Password
HOD	hod1	hod123
Faculty	faculty1	faculty123
Face Registration Workflow
Open Face Recognition Panel
Enter Student Roll Number
Capture 60 Photos
Build Embeddings
Start Attendance Recognition
AI Models Used

The system uses:

InsightFace Buffalo_L Model
ONNX Runtime Inference
Face Embeddings for Recognition
Current Functionalities
Student Registration
Face Embedding Generation
Live Recognition
Attendance Tracking
Dashboard Monitoring
Excel Reporting
Future Improvements
Cloud Database Integration
Multi-Camera Support
Mobile App Integration
Advanced Analytics Dashboard
Real-time Notifications
GPU Acceleration
Developer

Sunanda Manne
Artificial Intelligence & Machine Learning Engineer

GitHub:
sunandamanne616-droid

License

This project is developed for academic and research purposes.
