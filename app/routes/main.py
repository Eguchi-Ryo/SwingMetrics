import os
import uuid
from pathlib import Path
from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify, send_from_directory

from app.data.mock_data import benchmark_models, form_options, summary_stats
from app.services.analysis_job import (
    list_history as job_history,
    save_analysis as save_job_analysis,
    get_analysis_by_id as get_job_analysis,
    delete_analysis_by_id
)
from app.services.swing_service import build_chart_config, build_dashboard_summary

main_bp = Blueprint("main", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@main_bp.route("/videos/<path:filename>")
def serve_video(filename):
    target_file = UPLOAD_DIR / filename
    if not target_file.exists():
        return f"Video file not found: {target_file}", 404
    return send_from_directory(str(UPLOAD_DIR), filename, mimetype="video/mp4")


@main_bp.route("/api/jobs/<int:job_id>")
def get_job_status(job_id):
    job = get_job_analysis(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
def dashboard():
    try:
        raw_history = job_history() or []
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
def upload():
    if request.method == "POST":
        title = (request.form.get("title") or "打撃スイング解析").strip()
        angle = (request.form.get("angle") or "真横 (打者正面側 / サイド)").strip()
        video_file = request.files.get("file")

        video_url = ""
        if video_file and video_file.filename != "":
            file_ext = os.path.splitext(video_file.filename)[1] or ".mp4"
            filename = f"batting_{uuid.uuid4()}{file_ext}"
            saved_path = UPLOAD_DIR / filename
            video_file.save(str(saved_path))
            video_url = f"/videos/{filename}"

        payload = {
            "title": title,
            "sport": "野球 (打撃)",
            "angle": angle,
            "video_url": video_url,
        }
        saved = save_job_analysis(payload)
        return redirect(url_for("main.analysis", id=saved["id"]))

    return render_template("upload.html", form_options=form_options)


# お手本一覧画面
@main_bp.route("/models")
def models():
    return render_template(
        "models.html",
        models=benchmark_models,
        form_options=form_options  
    )


# お手本新規登録 & YOLO解析
@main_bp.route("/models/new", methods=["POST"])
def add_model():
    name = (request.form.get("name") or "カスタムお手本打撃").strip()
    angle = (request.form.get("angle") or "真横 (打者正面側 / サイド)").strip()
    video_file = request.files.get("file")

    if not video_file or video_file.filename == "":
        return redirect(url_for("main.models"))

    raw_filename = f"bm_raw_{uuid.uuid4()}.mp4"
    saved_path = UPLOAD_DIR / raw_filename
    video_file.save(str(saved_path))

    payload = {
        "title": f"[お手本] {name}",
        "sport": "野球 (打撃)",
        "angle": angle,
        "video_url": f"/videos/{raw_filename}",
    }
    saved_job = save_job_analysis(payload)

    new_benchmark = {
        "id": f"bm_{uuid.uuid4().hex[:8]}",
        "name": name,
        "sport": "野球 (打撃)",
        "angle": angle,
        "video_url": saved_job.get("annotated_video_url") or f"/videos/{raw_filename}",
        "target_angle": float(saved_job.get("current_angle") or 10.0),
        "frames": saved_job.get("frames") or [],
        "is_system": False
    }
    benchmark_models.append(new_benchmark)

    return redirect(url_for("main.models"))


@main_bp.route("/api/models/<string:model_id>/delete", methods=["POST", "DELETE"])
def delete_benchmark_model(model_id):
    global benchmark_models
    target = next((m for m in benchmark_models if m.get("id") == model_id), None)
    if not target or target.get("is_system", False):
        return jsonify({"error": "削除できないお手本モデルです"}), 403

    benchmark_models = [m for m in benchmark_models if m.get("id") != model_id]
    return jsonify({"success": True})


@main_bp.route("/api/analysis/<int:job_id>/delete", methods=["POST", "DELETE"])
def delete_analysis(job_id):
    delete_analysis_by_id(job_id)
    return jsonify({"success": True})


@main_bp.route("/analysis")
def analysis():
    swing_id = request.args.get("id")
    analysis_data = get_job_analysis(swing_id) if swing_id else get_job_analysis("latest")

    if not analysis_data:
        analysis_data = {
            "id": 0,
            "title": "打撃スイング解析",
            "sport": "野球 (打撃)",
            "angle": "真横 (サイド)",
            "status": "completed",
            "video_url": "",
            "current_angle": 10.5,
            "overall_score": 85,
            "metrics": [],
            "frames": []
        }

    return render_template(
        "analysis.html",
        analysis=analysis_data,
        benchmark_models=benchmark_models,
    )