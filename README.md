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

This project is developed for academic and research purposes.<img width="1124" height="793" alt="Screenshot 2026-05-24 at 1 17 26 PM" src="https://github.com/user-attachments/assets/d1f77c4d-3ddd-45ff-b333-f579dce2db5e" />

<img width="884" height="803" alt="Screenshot 2026-05-24 at 1 17 42 PM" src="https://github.com/user-attachments/assets/0a9aca65-1179-440f-96a0-194333fcbcbd" />
<img width="516" height="798" alt="Screenshot 2026-05-24 at 1 17 31 PM" src="https://github.com/user-attachments/assets/e1f0cfb9-fb50-482a-b205-5fb1f989d489" />
<img width="1124" height="793" alt="Screenshot 2026-05-24 at 1 17 26 PM" src="https://github.com/user-attachments/assets/93d62065-c066-4726-b27d-279d81fae3f3" />
<img width="637" height="786" alt="Screenshot 2026-05-24 at 1 17 16 PM" src="https://github.com/user-attachments/assets/a5ea21bf-63ac-4483-9341-b0a160fca115" />
<img width="595" height="558" alt="Screenshot 2026-05-24 at 1 01 13 PM" src="https://github.com/user-attachments/assets/3e9845b0-4810-4a9f-965c-4f9ef15f5544" />


