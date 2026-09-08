"""
JWT issuing/verification helpers plus decorators used to protect routes.
"""
from functools import wraps
from datetime import datetime, timezone

import jwt
from flask import request, jsonify, current_app, g

from models import User


def generate_token(user):
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "name": user.name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + current_app.config["JWT_EXPIRY"],
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"])
    return token


def decode_token(token):
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET"],
        algorithms=[current_app.config["JWT_ALGORITHM"]],
    )


def _extract_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def login_required(f):
    """Attaches g.current_user if a valid JWT is supplied, else 401."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            print(f"[auth] 401 on {request.path}: no Authorization header was sent by the browser")
            return jsonify({"error": "Missing authorization token"}), 401
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            print(f"[auth] 401 on {request.path}: token signature is valid but has expired")
            return jsonify({"error": "Session expired, please log in again"}), 401
        except jwt.InvalidTokenError as e:
            print(f"[auth] 401 on {request.path}: token failed to decode/verify ({e})")
            return jsonify({"error": "Invalid authorization token"}), 401

        user = User.query.get(int(payload["sub"]))
        if not user:
            print(f"[auth] 401 on {request.path}: token decoded fine but user id={payload.get('sub')} not found in the database")
            return jsonify({"error": "User no longer exists"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return wrapper


def role_required(role):
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if g.current_user.role != role:
                return jsonify({"error": f"This action requires a {role} account"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator


def roles_required(*roles):
    """Like role_required, but accepts any of several roles — e.g. an
    endpoint that both regular teachers and the admin can use."""

    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if g.current_user.role not in roles:
                return jsonify({"error": f"This action requires one of these accounts: {', '.join(roles)}"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator
