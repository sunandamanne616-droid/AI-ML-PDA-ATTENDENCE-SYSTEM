"""
Notification module — sends email/SMS after attendance marking.
Supports: SMTP email, Twilio SMS (optional), console fallback.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_FROM", "")

def send_email(to_email: str, subject: str, body: str) -> bool:
    if not SMTP_HOST or not SMTP_USER:
        print(f"[EMAIL-CONSOLE] To: {to_email} | Subject: {subject}")
        print(f"  Body: {body}")
        return True

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[EMAIL-SENT] {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL-ERROR] {to_email}: {e}")
        return False

def send_sms(to_phone: str, message: str) -> bool:
    if not TWILIO_SID or not TWILIO_TOKEN:
        print(f"[SMS-CONSOLE] To: {to_phone} | Message: {message}")
        return True

    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=message, from_=TWILIO_FROM, to=to_phone)
        print(f"[SMS-SENT] {to_phone}")
        return True
    except Exception as e:
        print(f"[SMS-ERROR] {to_phone}: {e}")
        return False

def notify_attendance(student_name: str, roll_no: str, subject: str,
                      date_str: str, status: str,
                      email: Optional[str] = None, phone: Optional[str] = None,
                      average: Optional[float] = None):
    # Only notify ABSENT students or those below 75% (saves Gmail quota)
    if status == "P" and (average is None or average >= 75):
        return

    status_text = "PRESENT ✅" if status == "P" else "ABSENT ❌"

    body = f"""
    <div style="font-family:Arial;padding:20px;max-width:500px;margin:auto;border:1px solid #ddd;border-radius:10px;">
        <h2 style="color:#1a73e8;">📋 Attendance Notification</h2>
        <p>Hello <b>{student_name}</b>,</p>
        <table style="width:100%;border-collapse:collapse;margin:15px 0;">
            <tr><td style="padding:8px;border-bottom:1px solid #eee;"><b>Subject</b></td><td style="padding:8px;border-bottom:1px solid #eee;">{subject}</td></tr>
            <tr><td style="padding:8px;border-bottom:1px solid #eee;"><b>Date</b></td><td style="padding:8px;border-bottom:1px solid #eee;">{date_str}</td></tr>
            <tr><td style="padding:8px;border-bottom:1px solid #eee;"><b>Status</b></td><td style="padding:8px;border-bottom:1px solid #eee;">{status_text}</td></tr>
            {"<tr><td style='padding:8px;border-bottom:1px solid #eee;'><b>Average</b></td><td style='padding:8px;border-bottom:1px solid #eee;'>" + f"{average:.1f}%" + "</td></tr>" if average is not None else ""}
        </table>
        {"<p style='color:red;font-weight:bold;'>⚠️ WARNING: Your attendance is below 75%. Please attend classes regularly!</p>" if average is not None and average < 75 else ""}
        <p style="color:#888;font-size:12px;">— AIML Attendance System</p>
    </div>
    """

    sms_text = f"AIML Attendance: {student_name} marked {status_text} for {subject} on {date_str}."
    if average is not None and average < 75:
        sms_text += f" WARNING: Average {average:.1f}% (below 75%)!"

    if email:
        send_email(email, f"Attendance: {status_text} for {subject} ({date_str})", body)
    if phone:
        send_sms(phone, sms_text)

def notify_hod_alert(message: str, hod_emails: list, principal_emails: list):
    all_emails = hod_emails + principal_emails
    body = f"""
    <div style="font-family:Arial;padding:20px;max-width:500px;margin:auto;border:2px solid red;border-radius:10px;">
        <h2 style="color:red;">🔴 Class Alert</h2>
        <p>{message}</p>
        <p style="color:#888;font-size:12px;">— AIML Attendance System (Automated Alert)</p>
    </div>
    """
    for email in all_emails:
        if email:
            send_email(email, f"🔴 ALERT: {message}", body)

def notify_low_attendance(student_name: str, roll_no: str, average: float,
                          email: Optional[str] = None):
    if not email:
        return
    body = f"""
    <div style="font-family:Arial;padding:20px;max-width:500px;margin:auto;border:2px solid orange;border-radius:10px;">
        <h2 style="color:orange;">⚠️ Low Attendance Warning</h2>
        <p>Hello <b>{student_name}</b> ({roll_no}),</p>
        <p>Your overall attendance average is <b style="color:red;">{average:.1f}%</b>, which is below the required 75%.</p>
        <p>Please attend classes regularly to avoid academic consequences.</p>
        <p style="color:#888;font-size:12px;">— AIML Attendance System</p>
    </div>
    """
    send_email(email, f"⚠️ Low Attendance Warning — {average:.1f}%", body)


