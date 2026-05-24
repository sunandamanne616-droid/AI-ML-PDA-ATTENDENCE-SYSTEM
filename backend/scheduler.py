"""
Background scheduler — checks timetable, monitors classes, sends alerts.
Runs every 60 seconds:
  1. 15 min after scheduled start with no attendance → alert HOD/Principal/Faculty
  2. Track missed classes in FacultyLog
  3. Monthly report email (1st of month)
  4. Daily shortage report (students below 75%) — sent every morning at 8:00 AM to HOD
"""
import asyncio
from datetime import datetime, date, timedelta
from backend.database import SessionLocal
from backend.models import TimetableSlot, LiveClassStatus, AlertLog, User, FacultyLog, Attendance, Student

async def check_class_schedule():
    """Run every 60 seconds to check classes and send shortage report at 8 AM."""
    while True:
        try:
            db = SessionLocal()
            now = datetime.now()
            day_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
            today_name = day_map.get(now.weekday(), "")
            current_time = now.strftime("%H:%M")

            # ── Daily shortage report at 8:00 AM ─────────────────────
            if now.hour == 8 and now.minute < 2:
                try:
                    await send_shortage_report(db)
                except Exception as e:
                    print(f"[SHORTAGE-REPORT-ERROR] {e}")

            # ── Find all slots for today ──────────────────────────────
            slots = db.query(TimetableSlot).filter(TimetableSlot.day_name == today_name).all()

            for slot in slots:
                slot_start = datetime.strptime(
                    f"{now.strftime('%Y-%m-%d')} {slot.start_time}", "%Y-%m-%d %H:%M"
                )
                minutes_in = (now - slot_start).total_seconds() / 60

                if 15 <= minutes_in <= 20:
                    from backend.live_routes import attendance_active, attendance_data
                    today = date.today()

                    existing_log = db.query(FacultyLog).filter(
                        FacultyLog.faculty_username == slot.faculty_username,
                        FacultyLog.subject == slot.subject,
                        FacultyLog.day == today,
                    ).first()

                    att_count = db.query(Attendance).filter(
                        Attendance.subject == slot.subject,
                        Attendance.semester == slot.semester,
                        Attendance.day == today,
                    ).count()

                    is_running = (
                        attendance_active
                        and attendance_data.get("subject") == slot.subject
                        and attendance_data.get("faculty_name") == slot.faculty_username
                    )

                    if not existing_log and att_count == 0 and not is_running:
                        existing_alert = db.query(AlertLog).filter(
                            AlertLog.alert_type == "no_class",
                            AlertLog.message.contains(slot.subject),
                            AlertLog.message.contains(slot.start_time),
                            AlertLog.created_at >= slot_start,
                        ).first()

                        if not existing_alert:
                            msg = (
                                f"{slot.subject} class ({slot.start_time}-{slot.end_time}) by "
                                f"{slot.faculty_username} has NOT STARTED. "
                                f"15 minutes past scheduled time."
                            )
                            alert = AlertLog(alert_type="no_class", message=msg)
                            db.add(alert)

                            missed_log = FacultyLog(
                                faculty_username=slot.faculty_username,
                                subject=slot.subject, semester=slot.semester,
                                day=today,
                                scheduled_start=slot.start_time,
                                scheduled_end=slot.end_time,
                                status="missed",
                            )
                            db.add(missed_log)
                            db.commit()

                            recipients = db.query(User).filter(
                                User.role.in_(["hod", "principal"])
                            ).all()
                            faculty_user = db.query(User).filter(
                                User.username == slot.faculty_username
                            ).first()

                            emails = [u.email for u in recipients if u.email]
                            if faculty_user and faculty_user.email:
                                emails.append(faculty_user.email)

                            try:
                                from backend.notification import notify_hod_alert
                                notify_hod_alert(msg, emails, [])
                            except Exception as e:
                                print(f"[SCHEDULER-EMAIL-ERROR] {e}")

                            print(f"[SCHEDULER] ALERT: {msg}")

            # ── Monthly summary (midnight on 1st) ─────────────────────
            if now.day == 1 and now.hour == 0 and now.minute < 2:
                try:
                    await send_monthly_summary(db, now)
                except Exception as e:
                    print(f"[MONTHLY-REPORT-ERROR] {e}")

            db.close()
        except Exception as e:
            print(f"[SCHEDULER-ERROR] {e}")

        await asyncio.sleep(60)

# ══════════════════════════════════════════════════════════
# SHORTAGE REPORT — Students below 75%
# ══════════════════════════════════════════════════════════

def _build_shortage_data(db, semester: int = None) -> dict:
    """
    Calculate all students below 75% attendance.
    Returns dict with: students list, counts, grouped by semester and section.
    """
    q = db.query(Student)
    if semester:
        q = q.filter(Student.semester == semester)
    try:
        students = q.order_by(Student.semester, Student.section, Student.roll_no).all()
    except Exception:
        students = q.order_by(Student.semester, Student.roll_no).all()

    shortage_students = []
    for st in students:
        records = db.query(Attendance).filter(Attendance.roll_no == st.roll_no).all()
        total = len(records)
        present = sum(1 for r in records if r.status == "P")
        pct = round((present / total) * 100, 1) if total > 0 else 0.0

        if total == 0:
            continue  # Skip students with no attendance data yet

        if pct < 75:
            # Subject-wise breakdown
            subj_data = {}
            for r in records:
                if r.subject not in subj_data:
                    subj_data[r.subject] = {"total": 0, "present": 0}
                subj_data[r.subject]["total"] += 1
                if r.status == "P":
                    subj_data[r.subject]["present"] += 1

            subjects = []
            for subj, d in subj_data.items():
                sp = round((d["present"] / d["total"]) * 100, 1) if d["total"] else 0
                subjects.append({
                    "subject": subj,
                    "total": d["total"],
                    "present": d["present"],
                    "absent": d["total"] - d["present"],
                    "percentage": sp,
                    "below_75": sp < 75,
                })
            subjects.sort(key=lambda x: x["percentage"])

            # Classes needed to reach 75%
            # Formula: (present + x) / (total + x) = 0.75 → x = (0.75*total - present) / 0.25
            needed = max(0, int((0.75 * total - present) / 0.25) + 1) if pct < 75 else 0

            shortage_students.append({
                "roll_no": st.roll_no,
                "name": st.name,
                "semester": st.semester,
                "section": getattr(st, "section", None) or "A",
                "email": st.email,
                "phone": st.phone,
                "total": total,
                "present": present,
                "absent": total - present,
                "percentage": pct,
                "classes_needed": needed,
                "subjects": subjects,
            })

    shortage_students.sort(key=lambda x: x["percentage"])
    return shortage_students

def _build_shortage_email(shortage_students: list, triggered_by: str = "Automated") -> str:
    """Build a rich HTML email body for the shortage report."""
    today_str = date.today().strftime("%d %B %Y")
    count = len(shortage_students)

    if count == 0:
        return f"""
        <div style="font-family:Arial;padding:24px;max-width:700px;margin:auto;border:2px solid #22c55e;border-radius:12px;">
            <h2 style="color:#22c55e;">✅ All Students Above 75% — {today_str}</h2>
            <p>Great news! No students are currently below the 75% attendance threshold.</p>
            <p style="color:#888;font-size:12px;">— AIML Attendance System ({triggered_by})</p>
        </div>"""

    # Group by semester + section
    grouped = {}
    for s in shortage_students:
        key = f"Semester {s['semester']} — Section {s['section']}"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(s)

    section_html = ""
    for grp_name, grp_students in sorted(grouped.items()):
        rows = ""
        for s in grp_students:
            # Subject badges for subjects below 75
            bad_subjects = [sub for sub in s["subjects"] if sub["below_75"]]
            subj_badges = " ".join(
                f'<span style="background:#fee2e2;color:#dc2626;padding:2px 7px;border-radius:10px;font-size:11px;margin:1px;display:inline-block">'
                f'{sub["subject"]} {sub["percentage"]}%</span>'
                for sub in bad_subjects
            )
            color = "#dc2626" if s["percentage"] < 60 else "#f97316"
            rows += f"""
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:10px 8px;font-weight:600;">{s['roll_no']}</td>
                <td style="padding:10px 8px;">{s['name']}</td>
                <td style="padding:10px 8px;text-align:center;">
                    <span style="background:{color};color:#fff;padding:3px 10px;border-radius:12px;font-weight:700;font-size:13px">
                        {s['percentage']}%
                    </span>
                </td>
                <td style="padding:10px 8px;text-align:center;">{s['present']}/{s['total']}</td>
                <td style="padding:10px 8px;text-align:center;color:#dc2626;font-weight:600">{s['classes_needed']} classes</td>
                <td style="padding:10px 8px;">{subj_badges if subj_badges else '—'}</td>
            </tr>"""

        section_html += f"""
        <div style="margin-bottom:24px;">
            <h3 style="color:#1e293b;border-left:4px solid #f97316;padding-left:10px;margin-bottom:10px">{grp_name} ({len(grp_students)} students)</h3>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                    <tr style="background:#f8fafc;color:#64748b;">
                        <th style="padding:8px;text-align:left;border-bottom:2px solid #e2e8f0;">Roll No</th>
                        <th style="padding:8px;text-align:left;border-bottom:2px solid #e2e8f0;">Name</th>
                        <th style="padding:8px;text-align:center;border-bottom:2px solid #e2e8f0;">Overall %</th>
                        <th style="padding:8px;text-align:center;border-bottom:2px solid #e2e8f0;">Present/Total</th>
                        <th style="padding:8px;text-align:center;border-bottom:2px solid #e2e8f0;">Classes Needed</th>
                        <th style="padding:8px;text-align:left;border-bottom:2px solid #e2e8f0;">Weak Subjects</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    return f"""
    <div style="font-family:Arial;padding:24px;max-width:750px;margin:auto;border:2px solid #f97316;border-radius:12px;">
        <div style="background:#fff7ed;padding:16px;border-radius:8px;margin-bottom:20px;">
            <h2 style="color:#ea580c;margin:0;">⚠️ Attendance Shortage Report</h2>
            <p style="color:#64748b;margin:6px 0 0;">{today_str} &nbsp;|&nbsp; Triggered by: {triggered_by}</p>
        </div>

        <div style="display:flex;gap:16px;margin-bottom:20px;">
            <div style="background:#fee2e2;padding:12px 20px;border-radius:8px;text-align:center;flex:1;">
                <div style="font-size:28px;font-weight:700;color:#dc2626;">{count}</div>
                <div style="color:#64748b;font-size:12px;">Students Below 75%</div>
            </div>
            <div style="background:#fef3c7;padding:12px 20px;border-radius:8px;text-align:center;flex:1;">
                <div style="font-size:28px;font-weight:700;color:#d97706;">{sum(1 for s in shortage_students if s['percentage'] < 60)}</div>
                <div style="color:#64748b;font-size:12px;">Critical (Below 60%)</div>
            </div>
            <div style="background:#f0fdf4;padding:12px 20px;border-radius:8px;text-align:center;flex:1;">
                <div style="font-size:28px;font-weight:700;color:#16a34a;">{sum(1 for s in shortage_students if 60 <= s['percentage'] < 75)}</div>
                <div style="color:#64748b;font-size:12px;">Warning (60–74%)</div>
            </div>
        </div>

        {section_html}

        <p style="color:#94a3b8;font-size:12px;margin-top:20px;border-top:1px solid #e2e8f0;padding-top:12px;">
            This report was generated automatically by the AIML Attendance System.<br>
            Students need to attend the specified number of consecutive classes to reach 75%.
        </p>
    </div>"""

async def send_shortage_report(db, semester: int = None, triggered_by: str = "Automated (Daily 8 AM)"):
    """
    Calculate students below 75% and email the HOD + Principal.
    Called automatically at 8 AM daily, or manually via API.
    """
    from backend.notification import send_email

    today = date.today()
    today_str = today.isoformat()

    # Avoid sending duplicate automated reports on same day
    if triggered_by.startswith("Automated"):
        existing = db.query(AlertLog).filter(
            AlertLog.alert_type == "shortage_report",
            AlertLog.message.contains(today_str),
        ).first()
        if existing:
            print(f"[SHORTAGE] Already sent today ({today_str}), skipping")
            return {"skipped": True, "reason": "Already sent today"}

    shortage_students = _build_shortage_data(db, semester)
    email_body = _build_shortage_email(shortage_students, triggered_by)
    count = len(shortage_students)

    # Send to all HODs and Principals
    recipients = db.query(User).filter(User.role.in_(["hod", "principal"])).all()
    sent_to = []
    for u in recipients:
        if u.email:
            success = send_email(
                u.email,
                f"⚠️ Attendance Shortage Report — {today.strftime('%d %b %Y')} ({count} students below 75%)",
                email_body
            )
            if success:
                sent_to.append(u.email)

    # Log in AlertLog
    log_msg = f"Shortage report sent on {today_str}: {count} students below 75%"
    db.add(AlertLog(
        alert_type="shortage_report",
        message=log_msg,
        sent_to=", ".join(sent_to) if sent_to else "console"
    ))
    db.commit()

    print(f"[SHORTAGE] Report sent to {sent_to} — {count} students below 75%")
    return {
        "sent": True,
        "count": count,
        "sent_to": sent_to,
        "date": today_str,
    }

# ══════════════════════════════════════════════════════════
# MONTHLY SUMMARY
# ══════════════════════════════════════════════════════════

async def send_monthly_summary(db, now):
    """Send monthly attendance summary to HOD and Principal."""
    from backend.notification import send_email

    last_month = (now.replace(day=1) - timedelta(days=1))
    month_name = last_month.strftime("%B %Y")
    month_start = last_month.replace(day=1)
    month_end = now.replace(day=1) - timedelta(days=1)

    existing = db.query(AlertLog).filter(
        AlertLog.alert_type == "monthly_report",
        AlertLog.message.contains(month_name),
    ).first()
    if existing:
        return

    logs = db.query(FacultyLog).filter(
        FacultyLog.day >= month_start.date(),
        FacultyLog.day <= month_end.date(),
    ).all()

    completed = sum(1 for l in logs if l.status == "completed")
    missed    = sum(1 for l in logs if l.status == "missed")
    total     = len(logs)

    faculty_stats = {}
    for l in logs:
        if l.faculty_username not in faculty_stats:
            faculty_stats[l.faculty_username] = {"completed": 0, "missed": 0, "total": 0}
        faculty_stats[l.faculty_username]["total"] += 1
        if l.status == "completed":
            faculty_stats[l.faculty_username]["completed"] += 1
        elif l.status == "missed":
            faculty_stats[l.faculty_username]["missed"] += 1

    faculty_rows = ""
    for f, s in sorted(faculty_stats.items()):
        pct = round((s["completed"] / s["total"]) * 100) if s["total"] else 0
        faculty_rows += (
            f"<tr><td style='padding:8px;border:1px solid #ddd'>{f}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;color:green'>{s['completed']}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;color:red'>{s['missed']}</td>"
            f"<td style='padding:8px;border:1px solid #ddd'>{s['total']}</td>"
            f"<td style='padding:8px;border:1px solid #ddd'>{pct}%</td></tr>"
        )

    body = f"""
    <div style="font-family:Arial;padding:20px;max-width:600px;margin:auto;border:1px solid #ddd;border-radius:10px;">
        <h2 style="color:#1a73e8;">📊 Monthly Attendance Report — {month_name}</h2>
        <table style="width:100%;border-collapse:collapse;margin:15px 0;">
            <tr><td style="padding:8px;"><b>Total Classes Scheduled</b></td><td>{total}</td></tr>
            <tr><td style="padding:8px;"><b>Classes Completed</b></td><td style="color:green">{completed}</td></tr>
            <tr><td style="padding:8px;"><b>Classes Missed</b></td><td style="color:red">{missed}</td></tr>
        </table>
        <h3>Faculty Performance</h3>
        <table style="width:100%;border-collapse:collapse;margin:10px 0;border:1px solid #ddd;">
            <tr style="background:#f1f5f9;">
                <th style="padding:8px;border:1px solid #ddd;">Faculty</th>
                <th style="padding:8px;border:1px solid #ddd;">Completed</th>
                <th style="padding:8px;border:1px solid #ddd;">Missed</th>
                <th style="padding:8px;border:1px solid #ddd;">Total</th>
                <th style="padding:8px;border:1px solid #ddd;">%</th>
            </tr>
            {faculty_rows}
        </table>
        <p style="color:#888;font-size:12px;">— AIML Attendance System (Automated Monthly Report)</p>
    </div>"""

    recipients = db.query(User).filter(User.role.in_(["hod", "principal"])).all()
    for u in recipients:
        if u.email:
            send_email(u.email, f"📊 Monthly Report — {month_name}", body)

    db.add(AlertLog(alert_type="monthly_report", message=f"Monthly report sent for {month_name}"))
    db.commit()
    print(f"[MONTHLY] Report sent for {month_name}")

async def start_scheduler():
    """Start the background scheduler."""
    print("[SCHEDULER] Background class monitor started (15-min alerts + daily shortage report + monthly report)")
    asyncio.create_task(check_class_schedule())

