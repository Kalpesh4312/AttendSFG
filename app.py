"""
AI-Driven Attendance System with Facial Recognition, Session Token, and
Geo-Fencing.

Run with:
    python app.py

Then open http://127.0.0.1:5000 in your browser.
"""
import os

from flask import Flask, render_template

from config import Config
from extensions import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # --- Register API blueprints -----------------------------------------
    from routes.auth_routes import auth_bp
    from routes.teacher_routes import teacher_bp
    from routes.student_routes import student_bp
    from routes.attendance_routes import attendance_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(attendance_bp)

    # --- Page routes (server-rendered shells; data is loaded via JS/API) -
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/register")
    def register_page():
        return render_template("register.html")

    @app.route("/forgot-password")
    def forgot_password_page():
        return render_template("forgot_password.html")

    @app.route("/teacher/dashboard")
    def teacher_dashboard_page():
        return render_template("teacher/dashboard.html")

    @app.route("/teacher/classes/<int:class_id>")
    def teacher_class_detail_page(class_id):
        return render_template("teacher/class_detail.html", class_id=class_id)

    @app.route("/teacher/subjects/<int:subject_id>")
    def teacher_subject_detail_page(subject_id):
        return render_template("teacher/subject_detail.html", subject_id=subject_id)

    @app.route("/teacher/sessions/<int:session_id>")
    def teacher_session_page(session_id):
        return render_template("teacher/session_live.html", session_id=session_id)

    @app.route("/student/dashboard")
    def student_dashboard_page():
        return render_template("student/dashboard.html")

    @app.route("/student/classes/<int:class_id>")
    def student_class_detail_page(class_id):
        return render_template("student/class_detail.html", class_id=class_id)

    @app.route("/student/subjects/<int:subject_id>")
    def student_subject_detail_page(subject_id):
        return render_template("student/subject_detail.html", subject_id=subject_id)

    @app.route("/student/enroll-face")
    def enroll_face_page():
        return render_template("student/enroll_face.html")

    @app.route("/student/mark-attendance")
    def mark_attendance_page():
        return render_template("student/mark_attendance.html")

    @app.route("/admin/dashboard")
    def admin_dashboard_page():
        # Reuses the same page/JS as the teacher dashboard — the API
        # already returns every class in the system for an admin account,
        # and the client-side scripts adapt their labels/permissions
        # based on the logged-in user's role.
        return render_template("teacher/dashboard.html")

    with app.app_context():
        os.makedirs(os.path.join(Config.BASE_DIR, "instance"), exist_ok=True)
        db.create_all()
        seed_admin(app)

    return app


def seed_admin(app):
    """Create the default admin account on first run, if none exists yet."""
    from werkzeug.security import generate_password_hash
    from models import User

    if User.query.filter_by(role="admin").first():
        return

    admin = User(
        name=app.config["ADMIN_NAME"],
        email=app.config["ADMIN_EMAIL"].strip().lower(),
        password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]),
        role="admin",
    )
    db.session.add(admin)
    db.session.commit()
    print("=" * 70)
    print(" Default admin account created:")
    print(f"   email:    {app.config['ADMIN_EMAIL']}")
    print(f"   password: {app.config['ADMIN_PASSWORD']}")
    print(" Log in at /login with these credentials. Change them via the")
    print(" ADMIN_EMAIL / ADMIN_PASSWORD environment variables.")
    print("=" * 70)


app = create_app()

if __name__ == "__main__":
    use_reloader = os.environ.get("FLASK_RELOAD") == "1"

    app.run(
        debug=True,
        use_reloader=use_reloader,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
