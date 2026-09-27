import hmac
import secrets
from functools import wraps

from flask import abort, current_app, redirect, request, session, url_for


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_protected(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token") or request.headers.get("X-CSRFToken", "")
            if not expected or not hmac.compare_digest(expected, supplied):
                abort(400, description="CSRF token is missing or invalid.")
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("is_admin") is not True:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def current_owner_key():
    """アカウントキー、またはブラウザーごとに分離したゲストキーを返す。"""
    if session.get("is_admin") is True:
        return None

    user_id = session.get("user_id")
    if type(user_id) is int:
        return f"user:{user_id}"

    guest_id = session.get("guest_id")
    if not isinstance(guest_id, str) or len(guest_id) < 32:
        guest_id = secrets.token_urlsafe(32)
        session["guest_id"] = guest_id
    # Cookieを一定期間保持し、ゲストが自分の非公開データへ戻れるようにする。
    session.permanent = True
    return f"guest:{guest_id}"


def account_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if type(session.get("user_id")) is not int:
            return redirect(url_for("main.user_login", next=url_for("main.dashboard")))
        return view(*args, **kwargs)

    return wrapped


def contributor_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("is_admin") is True or isinstance(session.get("user_id"), int):
            return view(*args, **kwargs)
        return redirect(url_for("main.user_login", next=url_for("main.models")))

    return wrapped


def authenticate_admin(username, password):
    expected_username = current_app.config.get("ADMIN_USERNAME", "")
    expected_password = current_app.config.get("ADMIN_PASSWORD", "")
    if not expected_username or not expected_password:
        return False
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(
        password, expected_password
    )
