"""
Database models for the AI-Driven Attendance System.

Roles
-----
User.role is either "teacher" or "student".

Structure
---------
A ClassRoom is a batch/section (e.g. "BTech Data Science — Section A")
that holds the student roster and one or more class-level teachers
(coordinators, who can manage the roster and create subjects).

A ClassRoom can contain multiple Subjects (e.g. "Data Ethics",
"Machine Learning"). Each Subject can be assigned to one or more of the
class's teachers, and attendance is tracked per Subject — each subject
gets its own sessions, records, and attendance report, since different
subjects meet at different times.

Relationships
-------------
ClassRoom  <--many-to-many-->  User (teachers)          via class_teachers
ClassRoom  <--many-to-many-->  User (students)          via class_students (enrollment)
ClassRoom  <--one-to-many-->   Subject
Subject    <--many-to-many-->  User (teachers)          via subject_teachers
Subject    <--one-to-many-->   AttendanceSession
AttendanceSession <--one-to-many--> AttendanceRecord
"""
import json
import random
import string
from datetime import datetime

from extensions import db


def _random_code(length):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ---------------------------------------------------------------------------
# Association tables
# ---------------------------------------------------------------------------

class_teachers = db.Table(
    "class_teachers",
    db.Column("class_id", db.Integer, db.ForeignKey("class_room.id"), primary_key=True),
    db.Column("teacher_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("assigned_at", db.DateTime, default=datetime.utcnow),
)

class_students = db.Table(
    "class_students",
    db.Column("class_id", db.Integer, db.ForeignKey("class_room.id"), primary_key=True),
    db.Column("student_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("enrolled_at", db.DateTime, default=datetime.utcnow),
)

subject_teachers = db.Table(
    "subject_teachers",
    db.Column("subject_id", db.Integer, db.ForeignKey("subject.id"), primary_key=True),
    db.Column("teacher_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("assigned_at", db.DateTime, default=datetime.utcnow),
)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'teacher' | 'student'
    enrollment_no = db.Column(db.String(50), nullable=True)  # students only

    # JSON-encoded list of 128 floats produced by face-api.js, set once the
    # student completes face enrollment. NULL until then.
    face_descriptor = db.Column(db.Text, nullable=True)
    face_enrolled_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Classes this user co-ordinates (if role == teacher)
    classes_taught = db.relationship(
        "ClassRoom", secondary=class_teachers, back_populates="teachers"
    )
    # Classes this user is enrolled in (if role == student)
    classes_enrolled = db.relationship(
        "ClassRoom", secondary=class_students, back_populates="students"
    )
    # Subjects this user is specifically assigned to teach
    subjects_taught = db.relationship(
        "Subject", secondary=subject_teachers, back_populates="teachers"
    )

    def set_face_descriptor(self, descriptor_list):
        self.face_descriptor = json.dumps(descriptor_list)
        self.face_enrolled_at = datetime.utcnow()

    def get_face_descriptor(self):
        if not self.face_descriptor:
            return None
        return json.loads(self.face_descriptor)

    def to_public_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "enrollment_no": self.enrollment_no,
            "face_enrolled": bool(self.face_descriptor),
        }


# ---------------------------------------------------------------------------
# ClassRoom  (a batch/section holding the student roster)
# ---------------------------------------------------------------------------

class ClassRoom(db.Model):
    __tablename__ = "class_room"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    section = db.Column(db.String(50), nullable=True)

    # Short code students can use to self-enroll (e.g. "7K2P9A")
    join_code = db.Column(db.String(20), unique=True, nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # The one teacher (among `teachers`) elevated to manage this class's
    # teacher roster with the same authority as an admin — everyone else
    # assigned to the class can still teach/take attendance, but only the
    # class teacher (or a global admin) can add, remove, or reassign who
    # else teaches this class.
    class_teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    class_teacher = db.relationship("User", foreign_keys=[class_teacher_id])

    teachers = db.relationship(
        "User", secondary=class_teachers, back_populates="classes_taught"
    )
    students = db.relationship(
        "User", secondary=class_students, back_populates="classes_enrolled"
    )
    subjects = db.relationship(
        "Subject", backref="class_room", lazy=True, cascade="all, delete-orphan",
        order_by="Subject.created_at",
    )

    @staticmethod
    def generate_join_code(length=6):
        for _ in range(20):
            code = _random_code(length)
            if not ClassRoom.query.filter_by(join_code=code).first():
                return code
        raise RuntimeError("Could not generate a unique join code")

    def to_dict(self, include_counts=True):
        data = {
            "id": self.id,
            "name": self.name,
            "section": self.section,
            "join_code": self.join_code,
            "created_at": self.created_at.isoformat(),
            "class_teacher": self.class_teacher.to_public_dict() if self.class_teacher else None,
        }
        if include_counts:
            data["student_count"] = len(self.students)
            data["teacher_count"] = len(self.teachers)
            data["subject_count"] = len(self.subjects)
        return data


# ---------------------------------------------------------------------------
# Subject  (e.g. "Data Ethics" within a class; owns its own sessions/reports)
# ---------------------------------------------------------------------------

class Subject(db.Model):
    __tablename__ = "subject"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("class_room.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teachers = db.relationship(
        "User", secondary=subject_teachers, back_populates="subjects_taught"
    )
    sessions = db.relationship(
        "AttendanceSession", backref="subject", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self, include_counts=True):
        data = {
            "id": self.id,
            "class_id": self.class_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "teachers": [t.to_public_dict() for t in self.teachers],
        }
        if include_counts:
            data["session_count"] = len(self.sessions)
        return data


# ---------------------------------------------------------------------------
# AttendanceSession  (a single live "take attendance now" window for a subject)
# ---------------------------------------------------------------------------

class AttendanceSession(db.Model):
    __tablename__ = "attendance_session"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    token = db.Column(db.String(20), unique=True, nullable=False)

    # Classroom GPS location captured when the teacher starts the session.
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    radius_meters = db.Column(db.Float, nullable=False)

    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=False)
    ended_early_at = db.Column(db.DateTime, nullable=True)

    records = db.relationship(
        "AttendanceRecord", backref="session", lazy=True, cascade="all, delete-orphan"
    )

    @staticmethod
    def generate_token(length=6):
        for _ in range(20):
            code = _random_code(length)
            if not AttendanceSession.query.filter_by(token=code).first():
                return code
        raise RuntimeError("Could not generate a unique session token")

    def is_currently_active(self):
        now = datetime.utcnow()
        if self.ended_early_at is not None:
            return False
        return self.start_time <= now <= self.end_time

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "class_id": self.subject.class_id if self.subject else None,
            "token": self.token,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "radius_meters": self.radius_meters,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "is_active": self.is_currently_active(),
            "present_count": len(self.records),
        }


# ---------------------------------------------------------------------------
# AttendanceRecord (one student successfully marked present in a session)
# ---------------------------------------------------------------------------

class AttendanceRecord(db.Model):
    __tablename__ = "attendance_record"
    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_session_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_session.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="present")

    face_distance = db.Column(db.Float, nullable=True)
    distance_meters = db.Column(db.Float, nullable=True)

    student = db.relationship("User", foreign_keys=[student_id])

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "subject_id": self.subject_id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "enrollment_no": self.student.enrollment_no if self.student else None,
            "marked_at": self.marked_at.isoformat(),
            "status": self.status,
            "face_distance": round(self.face_distance, 4) if self.face_distance is not None else None,
            "distance_meters": round(self.distance_meters, 2) if self.distance_meters is not None else None,
        }


# ---------------------------------------------------------------------------
# PendingVerification — OTP-based email verification (registration) and
# password reset. No User row exists yet for a pending registration; the
# real User is only created once the OTP is verified.
# ---------------------------------------------------------------------------

class PendingVerification(db.Model):
    __tablename__ = "pending_verification"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False, index=True)
    purpose = db.Column(db.String(20), nullable=False)  # 'register' | 'reset'

    otp_hash = db.Column(db.String(255), nullable=False)
    attempts = db.Column(db.Integer, default=0)

    # For 'register': JSON-encoded {name, password_hash, role, enrollment_no}
    # awaiting OTP confirmation before the real User row is created.
    payload = db.Column(db.Text, nullable=True)

    # For 'reset': set once the OTP has been verified, proving the user
    # completed step 2 before they're allowed to actually set a new
    # password in step 3. Single-use.
    reset_token = db.Column(db.String(64), nullable=True)
    reset_token_used = db.Column(db.Boolean, default=False)

    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def get_payload(self):
        return json.loads(self.payload) if self.payload else {}
