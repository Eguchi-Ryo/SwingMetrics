import os
import secrets
from pathlib import Path
from datetime import timedelta

from flask import Flask, session
from dotenv import load_dotenv

from app.routes.main import admin_login, main_bp
from app.security import csrf_token, current_owner_key
from app.services.database import build_database_url, initialize_database

load_dotenv()


def _persistent_secret_key(project_root):
    """Keep guest-session signatures stable across restarts in the data volume."""
    secret_path = project_root / "data" / ".flask_secret_key"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            secret_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        return secret_path.read_text(encoding="utf-8").strip()

    secret = secrets.token_urlsafe(48)
    with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
        secret_file.write(secret)
    return secret


def create_app(config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["JSON_SORT_KEYS"] = False
    project_root = Path(__file__).resolve().parents[1]
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or _persistent_secret_key(project_root)
    app.config.update(
        DATABASE_URL=build_database_url(),
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", str(project_root / "data" / "uploads")),
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_CONTENT_LENGTH", str(500 * 1024 * 1024))),
        ADMIN_USERNAME=os.getenv("ADMIN_USERNAME", ""),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", ""),
        ADMIN_LOGIN_PATH=os.getenv("ADMIN_LOGIN_PATH", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(days=180),
    )
    if config:
        app.config.update(config)

    admin_login_path = app.config["ADMIN_LOGIN_PATH"]
    admin_login_settings = (
        app.config["ADMIN_USERNAME"],
        app.config["ADMIN_PASSWORD"],
        admin_login_path,
    )
    if any(admin_login_settings) and not all(admin_login_settings):
        raise ValueError(
            "ADMIN_USERNAME, ADMIN_PASSWORD, and ADMIN_LOGIN_PATH must be configured together."
        )
    if admin_login_path:
        if (
            not admin_login_path.startswith("/")
            or admin_login_path.endswith("/")
            or "?" in admin_login_path
            or "#" in admin_login_path
            or len(admin_login_path) < 25
        ):
            raise ValueError(
                "ADMIN_LOGIN_PATH must be a non-public path of at least 24 characters, "
                "starting with '/' and without a trailing slash, query, or fragment."
            )

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    initialize_database(app.config["DATABASE_URL"])
    app.register_blueprint(main_bp)
    if admin_login_path:
        app.add_url_rule(
            admin_login_path,
            endpoint="main.admin_login",
            view_func=admin_login,
            methods=["GET", "POST"],
        )

    @app.context_processor
    def inject_admin_state():
        owner_key = current_owner_key()
        return {
            "is_admin": session.get("is_admin") is True,
            "is_guest": owner_key is not None and not session.get("username"),
            "current_user_id": session.get("user_id"),
            "current_username": session.get("username"),
            "csrf_token": csrf_token,
        }

    return app
