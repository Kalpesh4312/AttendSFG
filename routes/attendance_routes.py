"""
The heart of the system: a student submits

    { token, descriptor, latitude, longitude }

and this route runs all three security checks described in the project's
block diagram before writing an AttendanceRecord:

    1. Session token   -- must exist, belong to an enrolled class, and be
                          currently within its active time window.
    2. Facial recognition -- the live descriptor (captured client-side by
                          face-api.js) must be within FACE_MATCH_THRESHOLD
                          Euclidean distance of the student's enrolled
                          descriptor.
    3. Geo-fencing     -- the student's device coordinates must be within
                          the session's configured radius of the classroom
                          location.

All three must pass. Any failure returns a specific reason so the student
knows what to fix (out of range, face not recognized, token expired, etc.)
without silently failing.
"""
from datetime import datetime

from flask import Blueprint, request, jsonify, g, current_app

from extensions import db
from models import AttendanceSession, AttendanceRecord
from utils.auth import role_required
from utils.face import is_face_match, validate_descriptor
from utils.geo import is_within_geofence

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")


@attendance_bp.route("/mark", methods=["POST"])
@role_required("student")
def mark_attendance():
    student = g.current_user
    data = request.get_json(force=True, silent=True) or {}

    token = (data.get("token") or "").strip().upper()
    descriptor = data.get("descriptor")
    try:
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "Location not available. Please allow GPS/location access."}), 400

    if not token:
        return jsonify({"error": "Session token is required"}), 400

    # --- 1. Session token validity -----------------------------------
    session_obj = AttendanceSession.query.filter_by(token=token).first()
    if not session_obj:
        return jsonify({"error": "Invalid session token"}), 404

    subject = session_obj.subject
    classroom = subject.class_room
    if student not in classroom.students:
        return jsonify({"error": "You are not enrolled in this class"}), 403

    if not session_obj.is_currently_active():
        now = datetime.utcnow()
        if now < session_obj.start_time:
            reason = "This attendance session has not started yet"
        else:
            reason = "This attendance session token has expired"
        return jsonify({"error": reason, "reason_code": "TOKEN_EXPIRED"}), 400

    existing = AttendanceRecord.query.filter_by(
        session_id=session_obj.id, student_id=student.id
    ).first()
    if existing:
        return jsonify({"error": "Attendance already marked for this session", "reason_code": "ALREADY_MARKED"}), 409

    # --- 2. Facial recognition ----------------------------------------
    expected_len = current_app.config["FACE_DESCRIPTOR_LENGTH"]
    if not validate_descriptor(descriptor, expected_len):
        return jsonify({"error": "No face detected. Please center your face in the frame and try again.",
                         "reason_code": "NO_FACE"}), 400

    stored_descriptor = student.get_face_descriptor()
    if not stored_descriptor:
        return jsonify({"error": "You have not enrolled your face yet. Please complete face enrollment first.",
                         "reason_code": "NOT_ENROLLED"}), 400

    threshold = current_app.config["FACE_MATCH_THRESHOLD"]
    face_ok, face_distance = is_face_match(stored_descriptor, descriptor, threshold)
    if not face_ok:
        return jsonify({
            "error": "Face verification failed. This does not match the enrolled face on record.",
            "reason_code": "FACE_MISMATCH",
            "face_distance": round(face_distance, 4),
        }), 422

    # --- 3. Geo-fencing --------------------------------------------------
    geo_ok, distance = is_within_geofence(
        session_obj.latitude, session_obj.longitude, latitude, longitude, session_obj.radius_meters
    )
    if not geo_ok:
        return jsonify({
            "error": f"You are outside the classroom area ({round(distance)}m away, "
                     f"allowed radius {round(session_obj.radius_meters)}m).",
            "reason_code": "OUT_OF_RANGE",
            "distance_meters": round(distance, 2),
        }), 422

    # --- All checks passed: record attendance ----------------------------
    record = AttendanceRecord(
        session_id=session_obj.id,
        subject_id=subject.id,
        student_id=student.id,
        marked_at=datetime.utcnow(),
        status="present",
        face_distance=face_distance,
        distance_meters=distance,
    )
    db.session.add(record)
    db.session.commit()

    return jsonify({
        "message": "Attendance marked successfully",
        "record": record.to_dict(),
        "subject": subject.to_dict(),
        "class": classroom.to_dict(),
    }), 201
