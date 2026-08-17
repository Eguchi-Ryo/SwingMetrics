def build_dashboard_summary(history):
    if not history:
        return {"total": 0, "average": 0}

    total = len(history)
    valid_scores = []
    for item in history:
        if isinstance(item, dict):
            score = item.get("score") or item.get("overall_score")
            if score is not None:
                try:
                    valid_scores.append(float(score))
                except (ValueError, TypeError):
                    pass

    average = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0
    return {"total": total, "average": average}

def build_chart_config(labels, scores):
    return {
        "labels": labels if labels else ["-"],
        "datasets": [
            {
                "label": "打撃スコア推移",
                "data": scores if scores else [0],
                "borderColor": "#60a5fa",
                "backgroundColor": "rgba(96, 165, 250, 0.15)",
                "fill": True,
                "tension": 0.3,
            }
        ]
    }