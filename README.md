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
<<img width="690" height="319" alt="Screenshot 2026-05-24 at 1 17 10 PM" src="https://github.com/user-attachments/assets/3c7972b0-aae2-4ff7-8614-7be46797db58" />
<img width="1470" height="795" alt="Screenshot 2026-05-24 at 1 17 04 PM" src="https://github.com/user-attachments/assets/058e2e70-b35e-4d01-814f-2b47c45fa29e" />
<img width="703" height="638" alt="Screenshot 2026-05-24 at 1 16 50 PM" src="https://github.com/user-attachments/assets/a8666173-99bc-41e6-8b99-379369d6251e" />
<img width="884" height="803" alt="Screenshot 2026-05-24 at 1 17 42 PM" src="https://github.com/user-attachments/assets/01acf05e-d554-414c-a543-121336354a71" />
<img width="637" height="786" alt="Screenshot 2026-05-24 at 1 17 16 PM" src="https://github.com/user-attachments/assets/6c5b67a2-2a58-4192-9316-27c555219893" />
<img width="516" height="798" alt="Screenshot 2026-05-24 at 1 17 31 PM" src="https://github.com/user-attachments/assets/14d0eca8-418f-49c3-8e8d-53576ceda1ec" />
<img width="1124" height="793" alt="Screenshot 2026-05-24 at 1 17 26 PM" src="https://github.com/user-attachments/assets/1e033b36-9924-4f11-a17d-11df58c5c88f" />

