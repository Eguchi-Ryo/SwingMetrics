from flask import Blueprint, render_template, request

from app.data.mock_data import (
    analysis_details,
    benchmark_models,
    dashboard_history,
    form_options,
    score_history,
    summary_stats,
    get_analysis_by_id,
)
from app.services.swing_service import build_chart_config, build_dashboard_summary

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
def dashboard():
    summary = build_dashboard_summary(dashboard_history)
    chart_labels = ["7/1", "7/5", "7/10", "7/15", "7/20", "7/25", "7/28", "8/1", "8/5", "8/10"]
    return render_template(
        "dashboard.html",
        summary=summary,
        history=dashboard_history,
        trend_text=summary_stats["trend_text"],
        chart_config=build_chart_config(chart_labels, score_history),
    )


@main_bp.route("/upload")
def upload():
    return render_template("upload.html", form_options=form_options)


@main_bp.route("/models")
def models():
    return render_template("models.html", models=benchmark_models)


@main_bp.route("/analysis")
def analysis():
    # クエリパラメータからswing_idを取得（デフォルトはswing_001）
    swing_id = request.args.get("id", "swing_001")
    analysis_data = get_analysis_by_id(swing_id)
    return render_template(
        "analysis.html",
        analysis=analysis_data,
        benchmark_models=benchmark_models,
    )
