"""
Student-panel routes. Requires a valid student JWT (role_required("student")).
"""
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from extensions import db
from models import ClassRoom, Subject, AttendanceSession, AttendanceRecord
from utils.auth import role_required

student_bp = Blueprint("student", __name__, url_prefix="/api/student")


@student_bp.route("/classes", methods=["GET"])
@role_required("student")
def my_classes():
    classes = sorted(g.current_user.classes_enrolled, key=lambda c: c.name)
    return jsonify({"classes": [c.to_dict() for c in classes]}), 200


@student_bp.route("/classes/join", methods=["POST"])
@role_required("student")
def join_class():
    data = request.get_json(force=True, silent=True) or {}
    join_code = (data.get("join_code") or "").strip().upper()
    if not join_code:
        return jsonify({"error": "A class join code is required"}), 400

    classroom = ClassRoom.query.filter_by(join_code=join_code).first()
    if not classroom:
        return jsonify({"error": "No class found with that join code"}), 404

    if g.current_user in classroom.students:
        return jsonify({"error": "You are already enrolled in this class"}), 409

    classroom.students.append(g.current_user)
    db.session.commit()
    return jsonify({"class": classroom.to_dict()}), 201


@student_bp.route("/classes/<int:class_id>", methods=["GET"])
@role_required("student")
def class_detail(class_id):
    classroom = ClassRoom.query.get(class_id)
    if not classroom or g.current_user not in classroom.students:
        return jsonify({"error": "You are not enrolled in this class"}), 403

    return jsonify({
        "class": classroom.to_dict(),
        "teachers": [t.to_public_dict() for t in classroom.teachers],
        "subjects": [s.to_dict() for s in classroom.subjects],
    }), 200


@student_bp.route("/subjects/<int:subject_id>/attendance", methods=["GET"])
@role_required("student")
def my_subject_attendance(subject_id):
    subject = Subject.query.get(subject_id)
    if not subject:
        return jsonify({"error": "Subject not found"}), 404
    classroom = subject.class_room
    if g.current_user not in classroom.students:
        return jsonify({"error": "You are not enrolled in this class"}), 403

    sessions = AttendanceSession.query.filter_by(subject_id=subject.id).filter(
        AttendanceSession.start_time <= datetime.utcnow()
    ).order_by(AttendanceSession.start_time.asc()).all()

    records = AttendanceRecord.query.filter_by(
        subject_id=subject.id, student_id=g.current_user.id
    ).all()
    present_session_ids = {r.session_id for r in records}

    history = []
    for s in sessions:
        history.append({
            "session_id": s.id,
            "date": s.start_time.isoformat(),
            "status": "present" if s.id in present_session_ids else "absent",
        })

    total = len(sessions)
    present = len(present_session_ids & {s.id for s in sessions})
    percent = round((present / total) * 100, 1) if total else 0.0

    return jsonify({
        "subject": subject.to_dict(),
        "class": classroom.to_dict(),
        "total_sessions": total,
        "present_count": present,
        "attendance_percent": percent,
        "history": history,
    }), 200


@student_bp.route("/classes/<int:class_id>/attendance-overview", methods=["GET"])
@role_required("student")
def my_class_attendance_overview(class_id):
    """The student's own attendance broken down subject-by-subject for
    this class, plus a combined overall figure across every subject."""
    classroom = ClassRoom.query.get(class_id)
    if not classroom or g.current_user not in classroom.students:
        return jsonify({"error": "You are not enrolled in this class"}), 403

    now = datetime.utcnow()
    per_subject = []
    overall_present = 0
    overall_total = 0

    for subject in classroom.subjects:
        sessions = AttendanceSession.query.filter_by(subject_id=subject.id).filter(
            AttendanceSession.start_time <= now
        ).all()
        total = len(sessions)
        session_ids = {s.id for s in sessions}

        present = AttendanceRecord.query.filter_by(
            subject_id=subject.id, student_id=g.current_user.id
        ).filter(AttendanceRecord.session_id.in_(session_ids)).count() if session_ids else 0

        percent = round((present / total) * 100, 1) if total else 0.0
        per_subject.append({
            "subject_id": subject.id,
            "subject_name": subject.name,
            "sessions_present": present,
            "total_sessions": total,
            "attendance_percent": percent,
        })
        overall_present += present
        overall_total += total

    overall_percent = round((overall_present / overall_total) * 100, 1) if overall_total else 0.0

    return jsonify({
        "class": classroom.to_dict(),
        "per_subject": per_subject,
        "overall_present": overall_present,
        "overall_total": overall_total,
        "overall_percent": overall_percent,
    }), 200


@student_bp.route("/active-sessions", methods=["GET"])
@role_required("student")
def active_sessions():
    """Convenience endpoint: which subjects the student is enrolled in
    currently have a live attendance window open (so the UI can show a
    'Mark Attendance now' banner without the student needing the token in
    advance)."""
    now = datetime.utcnow()
    results = []
    for classroom in g.current_user.classes_enrolled:
        for subject in classroom.subjects:
            live = AttendanceSession.query.filter_by(subject_id=subject.id).filter(
                AttendanceSession.start_time <= now,
                AttendanceSession.end_time >= now,
                AttendanceSession.ended_early_at.is_(None),
            ).first()
            if live:
                results.append({
                    "class": classroom.to_dict(),
                    "subject": subject.to_dict(),
                    "session_id": live.id,
                })
    return jsonify({"active": results}), 200
