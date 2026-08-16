def format_score(score: int) -> str:
    return f"{score} / 100"


def get_benchmark_by_id(benchmarks, benchmark_id):
    return next((item for item in benchmarks if item["id"] == benchmark_id), benchmarks[0])


def build_dashboard_summary(history):
    total = len(history)
    average = sum(item["score"] for item in history) / total if total else 0

    return {
        "total": total,
        "average": round(average, 1),
        "latest_score": history[0]["score"] if history else 0,
        "improvement": 1.8,
    }


def build_chart_config(labels, series):
    return {
        "labels": labels,
        "datasets": [
            {
                "label": "インパクト前傾角度 (°)",
                "data": series,
                "borderColor": "#3b82f6",
                "backgroundColor": "rgba(59, 130, 246, 0.12)",
                "fill": True,
                "tension": 0.35,
                "borderWidth": 2,
            }
        ],
    }


def build_trend_metric(overall_score: int) -> str:
    if overall_score >= 85:
        return "Excellent"
    if overall_score >= 75:
        return "Good"
    return "Needs Focus"
