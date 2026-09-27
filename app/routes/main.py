import uuid
import re
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for, jsonify, send_from_directory
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app.data.options import FORM_OPTIONS
from app.security import (
    account_required,
    admin_required,
    authenticate_admin,
    contributor_required,
    csrf_protected,
    csrf_token,
    current_owner_key,
)
from app.services.database import payload_belongs_to_owner
from app.services.analysis_job import (
    can_view_analysis_video,
    list_history as job_history,
    save_analysis as save_job_analysis,
    get_analysis_by_id as get_job_analysis,
    delete_analysis_by_id
)
from app.services.benchmark_service import (
    can_view_benchmark_video,
    delete_benchmark_model as remove_benchmark_model,
    list_benchmark_models,
    save_benchmark_model,
    start_benchmark_analysis,
)
from app.services.swing_service import build_chart_config, build_dashboard_summary
from app.services.user_service import authenticate_user, create_user, transfer_guest_data

main_bp = Blueprint("main", __name__)


def _store_uploaded_video(video_file, prefix):
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_original_name = secure_filename(video_file.filename or "")
    file_ext = Path(safe_original_name).suffix.lower() or ".mp4"
    filename = f"{prefix}_{uuid.uuid4().hex}{file_ext}"
    saved_path = upload_dir / filename
    try:
        video_file.save(str(saved_path))
        if not saved_path.is_file() or saved_path.stat().st_size == 0:
            raise OSError("アップロードされた動画ファイルを保存できませんでした。")
    except Exception:
        saved_path.unlink(missing_ok=True)
        raise
    return filename, saved_path


def _safe_next_url(candidate):
    if not candidate:
        return url_for("main.dashboard")
    parsed = urlsplit(candidate)
    if (
        parsed.scheme
        or parsed.netloc
        or not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
    ):
        return url_for("main.dashboard")
    return candidate


@main_bp.route("/videos/<path:filename>")
def serve_video(filename):
    owner_key = current_owner_key()
    is_public_benchmark = can_view_benchmark_video(filename, owner_key=owner_key)
    is_owned_analysis = can_view_analysis_video(filename, owner_key=owner_key)
    if not (is_public_benchmark or is_owned_analysis):
        return "Video not found", 404
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    target_file = upload_dir / filename
    if not target_file.exists():
        return f"Video file not found: {target_file}", 404
    return send_from_directory(str(upload_dir), filename)


@main_bp.route("/api/jobs/<int:job_id>")
def get_job_status(job_id):
    job = get_job_analysis(job_id, owner_key=current_owner_key())
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/register", methods=["GET", "POST"])
@csrf_protected
def user_register():
    # 登録完了後に、現在のゲスト履歴を新しいアカウントへ移管する。
    guest_key = current_owner_key()
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not re.fullmatch(r"[a-z0-9_.-]{3,32}", username):
            error = "ユーザー名は英数字と . _ - を使った3〜32文字にしてください。"
        elif len(password) < 12:
            error = "パスワードは12文字以上にしてください。"
        else:
            try:
                user = create_user(username, password, current_app.config["DATABASE_URL"])
                transfer_guest_data(guest_key, user["id"], current_app.config["DATABASE_URL"])
            except IntegrityError:
                error = "このユーザー名は既に使用されています。"
            else:
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session.permanent = True
                csrf_token()
                return redirect(url_for("main.dashboard"))
    return render_template("user_register.html", error=error)


@main_bp.route("/login", methods=["GET", "POST"])
@csrf_protected
def user_login():
    # ゲスト利用中に蓄積した履歴を、ログイン先のアカウントへ移管する。
    guest_key = current_owner_key()
    error = None
    next_url = _safe_next_url(request.values.get("next", ""))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = authenticate_user(username, password, current_app.config["DATABASE_URL"])
        if user:
            transfer_guest_data(guest_key, user["id"], current_app.config["DATABASE_URL"])
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session.permanent = True
            csrf_token()
            return redirect(_safe_next_url(request.form.get("next", "")))
        error = "ユーザー名またはパスワードが正しくありません。"
    return render_template("user_login.html", error=error, next_url=next_url)


@main_bp.route("/logout", methods=["POST"])
@account_required
@csrf_protected
def user_logout():
    session.clear()
    return redirect(url_for("main.index"))


@csrf_protected
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if authenticate_admin(username, password):
            session.clear()
            session["is_admin"] = True
            csrf_token()
            return redirect(url_for("main.models"))
        error = "ユーザー名またはパスワードが正しくありません。"
    return render_template("admin_login.html", error=error)


@main_bp.route("/admin/logout", methods=["POST"])
@admin_required
@csrf_protected
def admin_logout():
    session.clear()
    return redirect(url_for("main.models"))


@main_bp.route("/dashboard")
def dashboard():
    owner_key = current_owner_key()
    try:
        raw_history = job_history(owner_key=owner_key) or []
    except Exception:
        raw_history = []

    normalized_history = [item for item in raw_history if isinstance(item, dict)]
    summary = build_dashboard_summary(normalized_history)

    sorted_history = sorted(normalized_history, key=lambda x: str(x.get("timestamp") or ""))
    chart_labels = [str(item.get("timestamp") or "")[:10] for item in sorted_history] or ["-"]
    chart_scores = [item.get("score") or item.get("overall_score") or 0 for item in sorted_history] or [0]

    return render_template(
        "dashboard.html",
        summary=summary,
        history=normalized_history,
        trend_text="直近の打撃解析履歴を確認できます。",
        chart_config=build_chart_config(chart_labels, chart_scores),
    )


@main_bp.route("/upload", methods=["GET", "POST"])
@csrf_protected
def upload():
    if request.method == "POST":
        title = (request.form.get("title") or "打撃スイング解析").strip()
        angle = (request.form.get("angle") or "真横 (打者正面側 / サイド)").strip()
        video_file = request.files.get("file")

        if not video_file or not video_file.filename:
            return "動画ファイルを選択してください。", 400

        saved_path = None
        try:
            filename, saved_path = _store_uploaded_video(video_file, "batting")
            video_url = f"/videos/{filename}"
            payload = {
                "title": title,
                "sport": "野球 (打撃)",
                "angle": angle,
                "video_url": video_url,
            }
            saved = save_job_analysis(payload, owner_key=current_owner_key())
        except Exception:
            if saved_path:
                saved_path.unlink(missing_ok=True)
            current_app.logger.exception("動画または解析情報の保存に失敗しました")
            return "動画を保存できませんでした。保存先とMySQLの接続を確認してください。", 500

        return redirect(url_for("main.analysis", id=saved["id"]))

    return render_template("upload.html", form_options=FORM_OPTIONS)


# お手本一覧画面
@main_bp.route("/models")
def models():
    owner_key = current_owner_key()
    models = list_benchmark_models(owner_key=owner_key)
    manageable_model_ids = [
        model["id"]
        for model in models
        if (session.get("is_admin") is True and model.get("is_official") is True)
        or (owner_key is not None and payload_belongs_to_owner(model, owner_key))
    ]
    return render_template(
        "models.html",
        models=models,
        form_options=FORM_OPTIONS,
        manageable_model_ids=manageable_model_ids,
        can_contribute=session.get("is_admin") is True or isinstance(session.get("user_id"), int),
    )


@main_bp.route("/api/models")
def get_benchmark_models():
    return jsonify(list_benchmark_models(owner_key=current_owner_key()))


# お手本新規登録 & YOLO解析
@main_bp.route("/models/new", methods=["POST"])
@contributor_required
@csrf_protected
def add_model():
    name = (request.form.get("name") or "").strip()
    angle = (request.form.get("angle") or "真横 (打者正面側 / サイド)").strip()
    video_file = request.files.get("file")

    if not name:
        return "お手本名を入力してください。", 400
    if not video_file or video_file.filename == "":
        return "お手本動画を選択してください。", 400

    is_official = session.get("is_admin") is True
    owner_id = None if is_official else session["user_id"]
    owner_key = None if is_official else current_owner_key()
    saved_path = None
    try:
        raw_filename, saved_path = _store_uploaded_video(video_file, "bm_raw")
        benchmark = save_benchmark_model({
            "name": name,
            "sport": "野球 (打撃)",
            "angle": angle,
            "video_url": f"/videos/{raw_filename}",
            "raw_video_url": f"/videos/{raw_filename}",
            "target_angle": 10.0,
            "frames": [],
            "metrics": [],
            "status": "processing",
            "progress": 0,
            "owner_id": owner_id,
            "owner_key": owner_key,
            "is_official": is_official,
        })
        start_benchmark_analysis(
            benchmark["id"],
            raw_filename,
            current_app.config["UPLOAD_FOLDER"],
            current_app.config["DATABASE_URL"],
        )
    except Exception:
        if "benchmark" in locals():
            remove_benchmark_model(
                benchmark["id"],
                owner_key=owner_key,
                is_admin=is_official,
            )
        if saved_path:
            saved_path.unlink(missing_ok=True)
        current_app.logger.exception("お手本動画または解析情報の保存に失敗しました")
        return "動画を保存できませんでした。保存先とMySQLの接続を確認してください。", 500

    return redirect(url_for("main.models"))


@main_bp.route("/api/models/<string:model_id>/delete", methods=["POST"])
@contributor_required
@csrf_protected
def delete_benchmark_model(model_id):
    owner_key = current_owner_key()
    target = remove_benchmark_model(
        model_id,
        owner_key=owner_key,
        is_admin=session.get("is_admin") is True,
    )
    if not target:
        return jsonify({"error": "お手本動画が見つかりません。"}), 404
    filenames = {
        Path(target.get(key, "")).name
        for key in ("video_url", "raw_video_url")
        if target.get(key)
    }
    for filename in filenames:
        video_path = Path(current_app.config["UPLOAD_FOLDER"]) / filename
        try:
            video_path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception("お手本動画ファイルを削除できませんでした: %s", filename)
    return jsonify({"success": True})


@main_bp.route("/api/analysis/<int:job_id>/delete", methods=["POST", "DELETE"])
@csrf_protected
def delete_analysis(job_id):
    owner_key = current_owner_key()
    analysis_data = get_job_analysis(job_id, owner_key=owner_key)
    if not analysis_data or not delete_analysis_by_id(job_id, owner_key=owner_key):
        return jsonify({"error": "Analysis not found"}), 404
    filenames = {
        Path(analysis_data.get(key, "")).name
        for key in ("video_url", "raw_video_url", "annotated_video_url")
        if analysis_data.get(key)
    }
    for filename in filenames:
        try:
            (Path(current_app.config["UPLOAD_FOLDER"]) / filename).unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception("解析動画を削除できませんでした: %s", filename)
    return jsonify({"success": True})


@main_bp.route("/analysis")
def analysis():
    swing_id = request.args.get("id")
    owner_key = current_owner_key()
    analysis_data = (
        get_job_analysis(swing_id, owner_key=owner_key)
        if swing_id
        else get_job_analysis("latest", owner_key=owner_key)
    )

    if not analysis_data:
        return "Analysis not found", 404

    benchmark_owner_key = None if session.get("is_admin") is True else owner_key

    return render_template(
        "analysis.html",
        analysis=analysis_data,
        benchmark_models=list_benchmark_models(owner_key=benchmark_owner_key),
    )