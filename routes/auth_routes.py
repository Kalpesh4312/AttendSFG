"""
Authentication routes.

Registration is a two-step flow:
    1. POST /register/request-otp   — validate fields, email a 6-digit OTP
    2. POST /register/verify-otp    — check the OTP, THEN create the User

No User row exists until step 2 succeeds, so every account in the
database is guaranteed to have a verified email address — there's no
separate "is_verified" flag to track.

Password reset is a three-step flow:
    1. POST /forgot-password/request-otp  — email a 6-digit OTP
    2. POST /forgot-password/verify-otp   — check the OTP, get a reset_token
    3. POST /forgot-password/reset        — set the new password using
                                             that (single-use) reset_token
"""
import json
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from models import User, PendingVerification
from utils.auth import generate_token, login_required
from utils.face import validate_descriptor
from utils.validators import validate_password_strength
from utils.email_utils import generate_otp, send_otp_email

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _otp_expiry():
    return datetime.utcnow() + timedelta(minutes=current_app.config["OTP_EXPIRY_MINUTES"])


def _issue_otp(email, purpose, payload=None):
    """Create (or replace) a pending OTP record for this email+purpose and
    email it. Returns the plaintext OTP (only ever used internally here —
    never returned to the client except in dev-mode)."""
    PendingVerification.query.filter_by(email=email, purpose=purpose).delete()

    otp = generate_otp(current_app.config["OTP_LENGTH"])
    record = PendingVerification(
        email=email,
        purpose=purpose,
        otp_hash=generate_password_hash(otp),
        payload=json.dumps(payload) if payload is not None else None,
        expires_at=_otp_expiry(),
    )
    db.session.add(record)
    db.session.commit()
    return otp


# ---------------------------------------------------------------------------
# Registration (with email OTP verification)
# ---------------------------------------------------------------------------

@auth_bp.route("/register/request-otp", methods=["POST"])
def register_request_otp():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "").strip().lower()
    enrollment_no = (data.get("enrollment_no") or "").strip() or None

    if not name or not email or not password or role not in ("teacher", "student"):
        return jsonify({"error": "name, email, password and a valid role are required"}), 400

    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Enter a valid email address"}), 400

    is_strong, missing = validate_password_strength(password)
    if not is_strong:
        return jsonify({"error": "Password does not meet requirements: " + "; ".join(missing)}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 409

    payload = {
        "name": name,
        "password_hash": generate_password_hash(password),
        "role": role,
        "enrollment_no": enrollment_no if role == "student" else None,
    }
    otp = _issue_otp(email, "register", payload)
    sent = send_otp_email(email, "register", otp)

    resp = {"message": f"A verification code has been sent to {email}."}
    if not sent:
        resp["dev_otp"] = otp  # dev-mode convenience only, see email_utils.py
        resp["message"] = "Email is not configured on this server (dev mode) — check the server console for your code."
    return jsonify(resp), 200


@auth_bp.route("/register/resend-otp", methods=["POST"])
def register_resend_otp():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    pending = PendingVerification.query.filter_by(email=email, purpose="register").first()
    if not pending:
        return jsonify({"error": "No pending registration found for this email. Please start again."}), 404

    otp = _issue_otp(email, "register", pending.get_payload())
    sent = send_otp_email(email, "register", otp)

    resp = {"message": f"A new verification code has been sent to {email}."}
    if not sent:
        resp["dev_otp"] = otp
        resp["message"] = "Email is not configured on this server (dev mode) — check the server console for your code."
    return jsonify(resp), 200


@auth_bp.route("/register/verify-otp", methods=["POST"])
def register_verify_otp():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()

    pending = PendingVerification.query.filter_by(email=email, purpose="register").first()
    if not pending:
        return jsonify({"error": "No pending registration found for this email. Please start again."}), 404

    if pending.is_expired():
        db.session.delete(pending)
        db.session.commit()
        return jsonify({"error": "This code has expired. Please request a new one."}), 400

    if pending.attempts >= current_app.config["OTP_MAX_ATTEMPTS"]:
        db.session.delete(pending)
        db.session.commit()
        return jsonify({"error": "Too many incorrect attempts. Please request a new code."}), 429

    if not check_password_hash(pending.otp_hash, otp):
        pending.attempts += 1
        db.session.commit()
        remaining = current_app.config["OTP_MAX_ATTEMPTS"] - pending.attempts
        return jsonify({"error": f"Incorrect code. {remaining} attempt(s) remaining."}), 400

    # OTP correct — create the real account now.
    payload = pending.get_payload()
    if User.query.filter_by(email=email).first():
        db.session.delete(pending)
        db.session.commit()
        return jsonify({"error": "An account with this email already exists"}), 409

    user = User(
        name=payload["name"],
        email=email,
        password_hash=payload["password_hash"],
        role=payload["role"],
        enrollment_no=payload.get("enrollment_no"),
    )
    db.session.add(user)
    db.session.delete(pending)
    db.session.commit()

    token = generate_token(user)
    return jsonify({"token": token, "user": user.to_public_dict()}), 201


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = generate_token(user)
    return jsonify({"token": token, "user": user.to_public_dict()}), 200


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"user": g.current_user.to_public_dict()}), 200


# ---------------------------------------------------------------------------
# Forgot password (OTP-based reset)
# ---------------------------------------------------------------------------

@auth_bp.route("/forgot-password/request-otp", methods=["POST"])
def forgot_password_request_otp():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "No account found with that email"}), 404

    otp = _issue_otp(email, "reset")
    sent = send_otp_email(email, "reset", otp)

    resp = {"message": f"A password reset code has been sent to {email}."}
    if not sent:
        resp["dev_otp"] = otp
        resp["message"] = "Email is not configured on this server (dev mode) — check the server console for your code."
    return jsonify(resp), 200


@auth_bp.route("/forgot-password/verify-otp", methods=["POST"])
def forgot_password_verify_otp():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()

    pending = PendingVerification.query.filter_by(email=email, purpose="reset").first()
    if not pending:
        return jsonify({"error": "No password reset was requested for this email. Please start again."}), 404

    if pending.is_expired():
        db.session.delete(pending)
        db.session.commit()
        return jsonify({"error": "This code has expired. Please request a new one."}), 400

    if pending.attempts >= current_app.config["OTP_MAX_ATTEMPTS"]:
        db.session.delete(pending)
        db.session.commit()
        return jsonify({"error": "Too many incorrect attempts. Please request a new code."}), 429

    if not check_password_hash(pending.otp_hash, otp):
        pending.attempts += 1
        db.session.commit()
        remaining = current_app.config["OTP_MAX_ATTEMPTS"] - pending.attempts
        return jsonify({"error": f"Incorrect code. {remaining} attempt(s) remaining."}), 400

    # OTP correct — issue a single-use reset token for the final step.
    reset_token = secrets.token_urlsafe(32)
    pending.reset_token = reset_token
    pending.reset_token_used = False
    pending.expires_at = _otp_expiry()  # give them a fresh window to set the new password
    db.session.commit()

    return jsonify({"reset_token": reset_token}), 200


@auth_bp.route("/forgot-password/reset", methods=["POST"])
def forgot_password_reset():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    reset_token = (data.get("reset_token") or "").strip()
    new_password = data.get("new_password") or ""

    pending = PendingVerification.query.filter_by(email=email, purpose="reset").first()
    if not pending or not pending.reset_token:
        return jsonify({"error": "Invalid or expired reset request. Please start again."}), 400

    if pending.reset_token_used or pending.reset_token != reset_token:
        return jsonify({"error": "Invalid or already-used reset link. Please start again."}), 400

    if pending.is_expired():
        db.session.delete(pending)
        db.session.commit()
        return jsonify({"error": "This reset session has expired. Please start again."}), 400

    is_strong, missing = validate_password_strength(new_password)
    if not is_strong:
        return jsonify({"error": "Password does not meet requirements: " + "; ".join(missing)}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Account no longer exists"}), 404

    user.password_hash = generate_password_hash(new_password)
    pending.reset_token_used = True
    db.session.delete(pending)
    db.session.commit()

    return jsonify({"message": "Password reset successfully. You can now log in."}), 200


# ---------------------------------------------------------------------------
# Face enrollment
# ---------------------------------------------------------------------------

@auth_bp.route("/face-enroll", methods=["POST"])
@login_required
def face_enroll():
    """Students capture their face via the browser (face-api.js) and submit
    the resulting 128-d descriptor here to be stored for future matching."""
    if g.current_user.role != "student":
        return jsonify({"error": "Only student accounts enroll a face"}), 403

    data = request.get_json(force=True, silent=True) or {}
    descriptor = data.get("descriptor")
    expected_len = current_app.config["FACE_DESCRIPTOR_LENGTH"]

    if not validate_descriptor(descriptor, expected_len):
        return jsonify({"error": f"A valid {expected_len}-value face descriptor is required"}), 400

    g.current_user.set_face_descriptor(descriptor)
    db.session.commit()

    return jsonify({"message": "Face enrolled successfully", "user": g.current_user.to_public_dict()}), 200
