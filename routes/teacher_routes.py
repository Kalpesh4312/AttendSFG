"""
Teacher-panel routes.

These endpoints accept either a "teacher" or "admin" account
(roles_required("teacher", "admin")) unless noted otherwise — admin can do
everything a teacher can, plus has blanket access to every class in the
system (not just ones they personally belong to).

Permission model
----------------
Only **admin** may create a class at all — teachers can never create one;
they can only be assigned to a class (and to subjects within it) by
admin or by that class's class teacher.

Within a class, most "structural" actions — adding/removing students,
adding/removing subjects, adding/removing/reassigning the class's teacher
list, and assigning which teacher covers which subject — are restricted
to:
  - the **admin**, or
  - the one teacher designated as this class's **class teacher**
    (ClassRoom.class_teacher_id).
Every other teacher assigned to the class can still view everything
(subjects, sessions, reports, roster) but cannot change the roster or
structure.

Starting or ending an attendance **session** for a subject is restricted
further still — not even the class teacher can do this unless they are
also specifically one of that subject's assigned teachers:
  - the **admin**, or
  - a teacher listed in that subject's own teacher list.

As a safeguard, the admin can never be removed from a class by anyone.
"""
import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g, current_app, Response

from extensions import db
from models import ClassRoom, Subject, User, AttendanceSession, AttendanceRecord
from utils.auth import roles_required, role_required

teacher_bp = Blueprint("teacher", __name__, url_prefix="/api/teacher")

STAFF_ROLES = ("teacher", "admin")


def _is_admin(user):
    return user.role == "admin"


def _get_owned_class_or_404(class_id):
    """Return the ClassRoom if the current user co-ordinates it — a class
    teacher-member, or an admin (who can access every class)."""
    classroom = ClassRoom.query.get(class_id)
    if not classroom:
        return None, jsonify({"error": "Class not found"}), 404
    if not _is_admin(g.current_user) and g.current_user not in classroom.teachers:
        return None, jsonify({"error": "You are not assigned to this class"}), 403
    return classroom, None, None


def _get_owned_subject_or_404(subject_id):
    """Return (subject, classroom) if the current user co-ordinates the
    subject's parent class. Access is at the class level by design."""
    subject = Subject.query.get(subject_id)
    if not subject:
        return None, None, jsonify({"error": "Subject not found"}), 404
    classroom = subject.class_room
    if not _is_admin(g.current_user) and g.current_user not in classroom.teachers:
        return None, None, jsonify({"error": "You are not assigned to this class"}), 403
    return subject, classroom, None, None


def _can_manage_class(classroom):
    """Only an admin, or the class's designated 'class teacher', may
    manage this class's structure: its teacher list, student roster, and
    subjects."""
    user = g.current_user
    if _is_admin(user):
        return True
    return classroom.class_teacher_id is not None and classroom.class_teacher_id == user.id


def _can_manage_sessions(subject):
    """Only an admin, or a teacher specifically assigned to THIS subject,
    may start or end an attendance session for it — being the class's
    overall class teacher is not enough on its own."""
    user = g.current_user
    if _is_admin(user):
        return True
    return user in subject.teachers


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

@teacher_bp.route("/classes", methods=["POST"])
@role_required("admin")
def create_class():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    section = (data.get("section") or "").strip() or None
    # Optional: create one or more subjects in the same step.
    subject_names = data.get("subjects") or []
    subject_names = [s.strip() for s in subject_names if isinstance(s, str) and s.strip()]

    if not name:
        return jsonify({"error": "Class name is required"}), 400

    classroom = ClassRoom(
        name=name,
        section=section,
        join_code="TEMP",
        created_by=g.current_user.id,
    )
    db.session.add(classroom)
    db.session.flush()  # get an id before generating a code check
    classroom.join_code = ClassRoom.generate_join_code(current_app.config["CLASS_JOIN_CODE_LENGTH"])
    classroom.teachers.append(g.current_user)
    # No class teacher is set yet — admin assigns one afterward from the
    # Teachers tab (a class always needs an admin-designated lead before a
    # regular teacher can manage its roster/subjects).

    for sub_name in subject_names:
        subject = Subject(name=sub_name, class_id=classroom.id, created_by=g.current_user.id)
        if not _is_admin(g.current_user):
            subject.teachers.append(g.current_user)
        db.session.add(subject)

    db.session.commit()

    return jsonify({"class": classroom.to_dict()}), 201


@teacher_bp.route("/classes", methods=["GET"])
@roles_required(*STAFF_ROLES)
def list_classes():
    if _is_admin(g.current_user):
        # Admin oversees every class in the system, not just ones they
        # personally belong to.
        classes = ClassRoom.query.order_by(ClassRoom.created_at.desc()).all()
    else:
        classes = sorted(g.current_user.classes_taught, key=lambda c: c.created_at, reverse=True)
    return jsonify({"classes": [c.to_dict() for c in classes]}), 200


@teacher_bp.route("/classes/<int:class_id>", methods=["GET"])
@roles_required(*STAFF_ROLES)
def class_detail(class_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code

    students = [s.to_public_dict() for s in sorted(classroom.students, key=lambda s: s.name)]
    teachers = [t.to_public_dict() for t in classroom.teachers]
    subjects = [s.to_dict() for s in classroom.subjects]

    return jsonify({
        "class": classroom.to_dict(),
        "students": students,
        "teachers": teachers,
        "subjects": subjects,
        "can_manage_class": _can_manage_class(classroom),
    }), 200


@teacher_bp.route("/classes/<int:class_id>", methods=["DELETE"])
@roles_required(*STAFF_ROLES)
def delete_class(class_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code
    db.session.delete(classroom)
    db.session.commit()
    return jsonify({"message": "Class deleted"}), 200


# ---------------------------------------------------------------------------
# Students within a class
# ---------------------------------------------------------------------------

@teacher_bp.route("/classes/<int:class_id>/students", methods=["POST"])
@roles_required(*STAFF_ROLES)
def add_student(class_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code
    if not _can_manage_class(classroom):
        return jsonify({"error": "Only the admin or this class's class teacher can add students"}), 403

    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Student email is required"}), 400

    student = User.query.filter_by(email=email, role="student").first()
    if not student:
        return jsonify({"error": "No student account found with that email"}), 404

    if student in classroom.students:
        return jsonify({"error": "Student already enrolled in this class"}), 409

    classroom.students.append(student)
    db.session.commit()
    return jsonify({"student": student.to_public_dict()}), 201


@teacher_bp.route("/classes/<int:class_id>/students/<int:student_id>", methods=["DELETE"])
@roles_required(*STAFF_ROLES)
def remove_student(class_id, student_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code
    if not _can_manage_class(classroom):
        return jsonify({"error": "Only the admin or this class's class teacher can remove students"}), 403

    student = User.query.get(student_id)
    if not student or student not in classroom.students:
        return jsonify({"error": "Student not enrolled in this class"}), 404

    classroom.students.remove(student)
    db.session.commit()
    return jsonify({"message": "Student removed from class"}), 200


# ---------------------------------------------------------------------------
# Teachers assigned to a class — restricted to admin / the class teacher
# ---------------------------------------------------------------------------

@teacher_bp.route("/classes/<int:class_id>/teachers", methods=["POST"])
@roles_required(*STAFF_ROLES)
def add_teacher(class_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code
    if not _can_manage_class(classroom):
        return jsonify({"error": "Only the admin or this class's class teacher can add teachers"}), 403

    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Teacher email is required"}), 400

    teacher = User.query.filter_by(email=email, role="teacher").first()
    if not teacher:
        return jsonify({"error": "No teacher account found with that email"}), 404

    if teacher in classroom.teachers:
        return jsonify({"error": "Teacher already assigned to this class"}), 409

    classroom.teachers.append(teacher)
    db.session.commit()
    return jsonify({"teacher": teacher.to_public_dict()}), 201


@teacher_bp.route("/classes/<int:class_id>/teachers/<int:teacher_id>", methods=["DELETE"])
@roles_required(*STAFF_ROLES)
def remove_teacher(class_id, teacher_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code
    if not _can_manage_class(classroom):
        return jsonify({"error": "Only the admin or this class's class teacher can remove teachers"}), 403

    teacher = User.query.get(teacher_id)
    if not teacher or teacher not in classroom.teachers:
        return jsonify({"error": "Teacher not assigned to this class"}), 404

    if _is_admin(teacher):
        return jsonify({"error": "The admin cannot be removed from a class"}), 403

    if len(classroom.teachers) <= 1:
        return jsonify({"error": "A class must keep at least one teacher"}), 400

    classroom.teachers.remove(teacher)
    if classroom.class_teacher_id == teacher.id:
        classroom.class_teacher_id = None
    # Also drop them from any subjects in this class.
    for subject in classroom.subjects:
        if teacher in subject.teachers:
            subject.teachers.remove(teacher)
    db.session.commit()
    return jsonify({"message": "Teacher removed from class"}), 200


@teacher_bp.route("/classes/<int:class_id>/class-teacher", methods=["POST"])
@role_required("admin")
def set_class_teacher(class_id):
    """Designate (or reassign) this class's elevated 'class teacher'.
    Admin-only — even the current class teacher can't hand off or change
    this designation themselves."""
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code

    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Teacher email is required"}), 400

    teacher = User.query.filter_by(email=email, role="teacher").first()
    if not teacher:
        return jsonify({"error": "No teacher account found with that email"}), 404

    # Auto-add them to the class's teacher roster if they aren't already on it.
    if teacher not in classroom.teachers:
        classroom.teachers.append(teacher)

    classroom.class_teacher_id = teacher.id
    db.session.commit()
    return jsonify({"class": classroom.to_dict()}), 200


@teacher_bp.route("/classes/<int:class_id>/class-teacher", methods=["DELETE"])
@role_required("admin")
def unset_class_teacher(class_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code

    classroom.class_teacher_id = None
    db.session.commit()
    return jsonify({"class": classroom.to_dict()}), 200


# ---------------------------------------------------------------------------
# Subjects within a class
# ---------------------------------------------------------------------------

@teacher_bp.route("/classes/<int:class_id>/subjects", methods=["POST"])
@roles_required(*STAFF_ROLES)
def create_subject(class_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code
    if not _can_manage_class(classroom):
        return jsonify({"error": "Only the admin or this class's class teacher can add subjects"}), 403

    data = request.get_json(force=True, silent=True) or {}

    # Support adding one subject {name: "..."} or several at once {names: [...]}.
    names = data.get("names")
    if names is None:
        single = (data.get("name") or "").strip()
        names = [single] if single else []
    names = [n.strip() for n in names if isinstance(n, str) and n.strip()]

    if not names:
        return jsonify({"error": "At least one subject name is required"}), 400

    created = []
    for n in names:
        subject = Subject(name=n, class_id=classroom.id, created_by=g.current_user.id)
        if not _is_admin(g.current_user):
            subject.teachers.append(g.current_user)
        db.session.add(subject)
        created.append(subject)
    db.session.commit()

    return jsonify({"subjects": [s.to_dict() for s in created]}), 201


@teacher_bp.route("/classes/<int:class_id>/subjects", methods=["GET"])
@roles_required(*STAFF_ROLES)
def list_subjects(class_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code
    return jsonify({"subjects": [s.to_dict() for s in classroom.subjects]}), 200


@teacher_bp.route("/subjects/<int:subject_id>", methods=["GET"])
@roles_required(*STAFF_ROLES)
def subject_detail(subject_id):
    subject, classroom, err, code = _get_owned_subject_or_404(subject_id)
    if err:
        return err, code

    sessions = sorted(subject.sessions, key=lambda s: s.start_time, reverse=True)
    return jsonify({
        "subject": subject.to_dict(),
        "class": classroom.to_dict(),
        "class_teachers": [t.to_public_dict() for t in classroom.teachers],
        "sessions": [s.to_dict() for s in sessions],
        "can_manage_class": _can_manage_class(classroom),
        "can_manage_sessions": _can_manage_sessions(subject),
    }), 200


@teacher_bp.route("/subjects/<int:subject_id>", methods=["DELETE"])
@roles_required(*STAFF_ROLES)
def delete_subject(subject_id):
    subject, classroom, err, code = _get_owned_subject_or_404(subject_id)
    if err:
        return err, code
    if not _can_manage_class(classroom):
        return jsonify({"error": "Only the admin or this class's class teacher can delete subjects"}), 403
    db.session.delete(subject)
    db.session.commit()
    return jsonify({"message": "Subject deleted"}), 200


@teacher_bp.route("/subjects/<int:subject_id>/teachers", methods=["POST"])
@roles_required(*STAFF_ROLES)
def assign_subject_teacher(subject_id):
    subject, classroom, err, code = _get_owned_subject_or_404(subject_id)
    if err:
        return err, code
    if not _can_manage_class(classroom):
        return jsonify({"error": "Only the admin or this class's class teacher can assign subject teachers"}), 403

    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Teacher email is required"}), 400

    teacher = User.query.filter_by(email=email, role="teacher").first()
    if not teacher or teacher not in classroom.teachers:
        return jsonify({"error": "That teacher must first be added to the class (Teachers tab) before being assigned to a subject"}), 404

    if teacher in subject.teachers:
        return jsonify({"error": "Teacher already assigned to this subject"}), 409

    subject.teachers.append(teacher)
    db.session.commit()
    return jsonify({"teacher": teacher.to_public_dict()}), 201


@teacher_bp.route("/subjects/<int:subject_id>/teachers/<int:teacher_id>", methods=["DELETE"])
@roles_required(*STAFF_ROLES)
def remove_subject_teacher(subject_id, teacher_id):
    subject, classroom, err, code = _get_owned_subject_or_404(subject_id)
    if err:
        return err, code
    if not _can_manage_class(classroom):
        return jsonify({"error": "Only the admin or this class's class teacher can remove subject teachers"}), 403

    teacher = User.query.get(teacher_id)
    if not teacher or teacher not in subject.teachers:
        return jsonify({"error": "Teacher not assigned to this subject"}), 404

    subject.teachers.remove(teacher)
    db.session.commit()
    return jsonify({"message": "Teacher removed from subject"}), 200


# ---------------------------------------------------------------------------
# Attendance sessions (facial recognition + session token + geofencing window)
# ---------------------------------------------------------------------------

@teacher_bp.route("/subjects/<int:subject_id>/sessions", methods=["POST"])
@roles_required(*STAFF_ROLES)
def start_session(subject_id):
    subject, classroom, err, code = _get_owned_subject_or_404(subject_id)
    if err:
        return err, code
    if not _can_manage_sessions(subject):
        return jsonify({"error": "Only the admin or a teacher assigned to this subject can start an attendance session"}), 403

    data = request.get_json(force=True, silent=True) or {}
    try:
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "A valid classroom latitude/longitude is required (allow location access)"}), 400

    duration_minutes = data.get("duration_minutes") or current_app.config["DEFAULT_SESSION_DURATION_MINUTES"]
    radius_meters = data.get("radius_meters") or current_app.config["DEFAULT_GEOFENCE_RADIUS_METERS"]

    try:
        duration_minutes = max(1, min(180, int(duration_minutes)))
        radius_meters = max(4, min(5000, float(radius_meters)))
    except (TypeError, ValueError):
        return jsonify({"error": "duration_minutes and radius_meters must be numeric"}), 400

    now = datetime.utcnow()
    session_obj = AttendanceSession(
        subject_id=subject.id,
        created_by=g.current_user.id,
        token=AttendanceSession.generate_token(current_app.config["SESSION_TOKEN_LENGTH"]),
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        start_time=now,
        end_time=now + timedelta(minutes=duration_minutes),
    )
    db.session.add(session_obj)
    db.session.commit()

    return jsonify({"session": session_obj.to_dict()}), 201


@teacher_bp.route("/subjects/<int:subject_id>/sessions", methods=["GET"])
@roles_required(*STAFF_ROLES)
def list_sessions(subject_id):
    subject, classroom, err, code = _get_owned_subject_or_404(subject_id)
    if err:
        return err, code

    sessions = AttendanceSession.query.filter_by(subject_id=subject.id).order_by(
        AttendanceSession.start_time.desc()
    ).all()
    return jsonify({"sessions": [s.to_dict() for s in sessions]}), 200


def _get_session_and_owned_class_or_404(session_id):
    session_obj = AttendanceSession.query.get(session_id)
    if not session_obj:
        return None, None, None, jsonify({"error": "Session not found"}), 404
    subject = session_obj.subject
    classroom = subject.class_room
    if not _is_admin(g.current_user) and g.current_user not in classroom.teachers:
        return None, None, None, jsonify({"error": "You are not assigned to this class"}), 403
    return session_obj, subject, classroom, None, None


@teacher_bp.route("/sessions/<int:session_id>", methods=["GET"])
@roles_required(*STAFF_ROLES)
def session_detail(session_id):
    session_obj, subject, classroom, err, code = _get_session_and_owned_class_or_404(session_id)
    if err:
        return err, code

    present_records = AttendanceRecord.query.filter_by(session_id=session_obj.id).order_by(
        AttendanceRecord.marked_at.asc()
    ).all()
    present_ids = {r.student_id for r in present_records}
    absent_students = [s.to_public_dict() for s in classroom.students if s.id not in present_ids]

    return jsonify({
        "session": session_obj.to_dict(),
        "subject": subject.to_dict(),
        "class": classroom.to_dict(),
        "present": [r.to_dict() for r in present_records],
        "absent": absent_students,
    }), 200


@teacher_bp.route("/sessions/<int:session_id>/end", methods=["POST"])
@roles_required(*STAFF_ROLES)
def end_session(session_id):
    session_obj, subject, classroom, err, code = _get_session_and_owned_class_or_404(session_id)
    if err:
        return err, code
    if not _can_manage_sessions(subject):
        return jsonify({"error": "Only the admin or a teacher assigned to this subject can end this session"}), 403

    session_obj.ended_early_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"session": session_obj.to_dict()}), 200


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def _build_subject_report(subject, classroom):
    sessions = AttendanceSession.query.filter_by(subject_id=subject.id).filter(
        AttendanceSession.start_time <= datetime.utcnow()
    ).order_by(AttendanceSession.start_time.asc()).all()

    total_sessions = len(sessions)
    session_ids = [s.id for s in sessions]

    records = []
    if session_ids:
        records = AttendanceRecord.query.filter(AttendanceRecord.session_id.in_(session_ids)).all()

    present_count_by_student = {}
    for r in records:
        present_count_by_student[r.student_id] = present_count_by_student.get(r.student_id, 0) + 1

    rows = []
    for student in sorted(classroom.students, key=lambda s: s.name):
        present = present_count_by_student.get(student.id, 0)
        pct = round((present / total_sessions) * 100, 1) if total_sessions else 0.0
        rows.append({
            "student_id": student.id,
            "name": student.name,
            "enrollment_no": student.enrollment_no,
            "email": student.email,
            "sessions_present": present,
            "total_sessions": total_sessions,
            "attendance_percent": pct,
        })
    return rows, total_sessions


@teacher_bp.route("/subjects/<int:subject_id>/attendance-report", methods=["GET"])
@roles_required(*STAFF_ROLES)
def subject_attendance_report(subject_id):
    subject, classroom, err, code = _get_owned_subject_or_404(subject_id)
    if err:
        return err, code

    rows, total_sessions = _build_subject_report(subject, classroom)
    return jsonify({
        "subject": subject.to_dict(), "class": classroom.to_dict(),
        "total_sessions": total_sessions, "report": rows,
    }), 200


@teacher_bp.route("/subjects/<int:subject_id>/attendance-report/export", methods=["GET"])
@roles_required(*STAFF_ROLES)
def export_subject_attendance_report(subject_id):
    subject, classroom, err, code = _get_owned_subject_or_404(subject_id)
    if err:
        return err, code

    rows, total_sessions = _build_subject_report(subject, classroom)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Enrollment No", "Email", "Sessions Present", "Total Sessions", "Attendance %"])
    for row in rows:
        writer.writerow([
            row["name"], row["enrollment_no"], row["email"],
            row["sessions_present"], row["total_sessions"], row["attendance_percent"],
        ])

    filename = f"attendance_{classroom.name}_{subject.name}.csv".replace(" ", "_")
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@teacher_bp.route("/classes/<int:class_id>/attendance-overview", methods=["GET"])
@roles_required(*STAFF_ROLES)
def class_attendance_overview(class_id):
    """Attendance matrix across every subject in the class: one row per
    student, one column per subject (percentage), plus a final combined
    'Overall' column — an at-a-glance view for whoever manages the class."""
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code

    matrix_rows, subject_summaries = _build_class_attendance_matrix(classroom)

    return jsonify({
        "class": classroom.to_dict(),
        "subjects": subject_summaries,
        "rows": matrix_rows,
    }), 200


def _build_class_attendance_matrix(classroom):
    """Shared by the JSON endpoint and the CSV export so both always
    agree on the numbers."""
    subject_summaries = []
    per_subject_rows = {}  # subject_id -> {student_id: row}
    per_student_present_total = {s.id: 0 for s in classroom.students}
    per_student_grand_total = {s.id: 0 for s in classroom.students}

    for subject in classroom.subjects:
        rows, total_sessions = _build_subject_report(subject, classroom)
        subject_summaries.append({
            "subject_id": subject.id,
            "subject_name": subject.name,
            "total_sessions": total_sessions,
        })
        per_subject_rows[subject.id] = {r["student_id"]: r for r in rows}
        for row in rows:
            per_student_present_total[row["student_id"]] += row["sessions_present"]
            per_student_grand_total[row["student_id"]] += row["total_sessions"]

    matrix_rows = []
    for student in sorted(classroom.students, key=lambda s: s.name):
        per_subject = {}
        for subject in classroom.subjects:
            row = per_subject_rows[subject.id].get(student.id)
            per_subject[str(subject.id)] = {
                "sessions_present": row["sessions_present"] if row else 0,
                "total_sessions": row["total_sessions"] if row else 0,
                "attendance_percent": row["attendance_percent"] if row else 0.0,
            }

        overall_present = per_student_present_total.get(student.id, 0)
        overall_total = per_student_grand_total.get(student.id, 0)
        overall_percent = round((overall_present / overall_total) * 100, 1) if overall_total else 0.0

        matrix_rows.append({
            "student_id": student.id,
            "name": student.name,
            "enrollment_no": student.enrollment_no,
            "per_subject": per_subject,
            "overall_present": overall_present,
            "overall_total": overall_total,
            "overall_percent": overall_percent,
        })

    return matrix_rows, subject_summaries


@teacher_bp.route("/classes/<int:class_id>/attendance-overview/export", methods=["GET"])
@roles_required(*STAFF_ROLES)
def export_class_attendance_overview(class_id):
    classroom, err, code = _get_owned_class_or_404(class_id)
    if err:
        return err, code

    matrix_rows, subject_summaries = _build_class_attendance_matrix(classroom)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    header = ["Name", "Enrollment No"] + [s["subject_name"] + " %" for s in subject_summaries] + ["Overall %"]
    writer.writerow(header)
    for row in matrix_rows:
        line = [row["name"], row["enrollment_no"]]
        for s in subject_summaries:
            line.append(row["per_subject"][str(s["subject_id"])]["attendance_percent"])
        line.append(row["overall_percent"])
        writer.writerow(line)

    filename = f"attendance_matrix_{classroom.name}.csv".replace(" ", "_")
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
