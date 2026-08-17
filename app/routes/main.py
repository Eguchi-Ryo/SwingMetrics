import os
import uuid
from pathlib import Path
from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify, send_from_directory

from app.data.mock_data import (
    benchmark_models,
    form_options,
    summary_stats,
    score_history,
)
from app.services.analysis_job import (
    list_history as job_history,
    save_analysis as save_job_analysis,
    get_analysis_by_id as get_job_analysis
)
from app.services.swing_service import build_chart_config, build_dashboard_summary

main_bp = Blueprint("main", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@main_bp.route("/videos/<path:filename>")
def serve_video(filename):
    """保存された動画ファイルをブラウザへ配信"""
    target_file = UPLOAD_DIR / filename
    if not target_file.exists():
        return f"Video file not found on server: {target_file}", 404
        
    return send_from_directory(str(UPLOAD_DIR), filename, mimetype="video/mp4")


@main_bp.route("/api/jobs/<int:job_id>")
def get_job_status(job_id):
    """解析の進捗・ステータスをJSONで返すAPI"""
    job = get_job_analysis(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
def dashboard():
    history = job_history()
    summary = build_dashboard_summary(history)
    chart_labels = ["7/1", "7/5", "7/10", "7/15", "7/20", "7/25", "7/28", "8/1", "8/5", "8/10"]
    summary_stats["total_analyses"] = len(history)
    summary_stats["average_score"] = summary["average"]

    return render_template(
        "dashboard.html",
        summary=summary,
        history=history,
        trend_text=summary_stats["trend_text"],
        chart_config=build_chart_config(chart_labels, score_history),
    )


@main_bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        title = (request.form.get("title") or "新規解析").strip()
        sport = (request.form.get("sport") or "ゴルフ (Golf)").strip()
        angle = (request.form.get("angle") or "真横 (サイド)").strip()
        model = (request.form.get("model") or "比較モデル 1").strip()
        video_file = request.files.get("file")

        video_url = ""
        if video_file and video_file.filename != "":
            file_ext = os.path.splitext(video_file.filename)[1] or ".mp4"
            filename = f"{uuid.uuid4()}{file_ext}"
            saved_path = UPLOAD_DIR / filename
            video_file.save(str(saved_path))
            video_url = f"/videos/{filename}"

        payload = {
            "title": title,
            "sport": sport,
            "angle": angle,
            "model": model,
            "video_url": video_url,
            "target_angle": 41.5,
            "current_angle": 38.2,
            "duration_ms": 3000,
        }
        session["latest_upload"] = payload
        saved = save_job_analysis(payload)
        return redirect(url_for("main.analysis", id=saved["id"]))

    return render_template("upload.html", form_options=form_options)


@main_bp.route("/models")
def models():
    return render_template("models.html", models=benchmark_models)


@main_bp.route("/analysis")
def analysis():
    swing_id = request.args.get("id")
    analysis_data = get_job_analysis(swing_id) if swing_id else get_job_analysis("latest")

    return render_template(
        "analysis.html",
        analysis=analysis_data,
        benchmark_models=benchmark_models,
    )