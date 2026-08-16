import json
import os
from pathlib import Path

# JSONデータファイルのパスを取得
DATA_DIR = Path(__file__).parent
DATA_FILE = DATA_DIR / "swing_data.json"


def load_swing_data():
    """JSONファイルからスイングデータを読み込む"""
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"swings": [], "benchmark_models": []}


# JSONデータを読み込む
_swing_data = load_swing_data()

# ダッシュボード履歴の構築
dashboard_history = [
    {
        "id": i + 1,
        "title": swing.get("title", ""),
        "sport": swing.get("sport", ""),
        "angle": swing.get("angle", ""),
        "score": swing.get("overall_score", 0),
        "timestamp": swing.get("timestamp", ""),
        "trend": ["stable", "up", "down"][i % 3],
    }
    for i, swing in enumerate(_swing_data.get("swings", []))
]

# ベンチマークモデルの構築
benchmark_models = [
    {
        "id": model.get("id", ""),
        "name": model.get("name", ""),
        "sport": model.get("sport", ""),
        "type": model.get("type", "pro"),
        "angle": model.get("metrics", {}).get("spine_angle", 0),
    }
    for model in _swing_data.get("benchmark_models", [])
]

summary_stats = {
    "total_analyses": len(_swing_data.get("swings", [])),
    "average_score": sum(s.get("overall_score", 0) for s in _swing_data.get("swings", [])) / max(len(_swing_data.get("swings", [])), 1),
    "trend_text": "前傾角度の平均ブレ幅が -1.8° 改善しています。インパクトでの起き上がり頻度が減少傾向にあります。",
}

score_history = [32, 33, 31, 35, 34, 36, 35, 37, 37.5, 38.2]


def get_analysis_by_id(swing_id: str = "swing_001"):
    """スイングIDに基づいて分析詳細を取得"""
    swings = _swing_data.get("swings", [])
    swing = next((s for s in swings if s.get("id") == swing_id), swings[0] if swings else {})
    
    if not swing:
        return None
    
    # ベンチマークモデルを取得
    benchmark_id = swing.get("benchmark_id", "")
    benchmark = next(
        (m for m in _swing_data.get("benchmark_models", []) if m.get("id") == benchmark_id),
        None
    )
    
    impact_metrics = swing.get("metrics_at_impact", {})
    benchmark_metrics = benchmark.get("metrics", {}) if benchmark else {}
    
    return {
        "id": swing.get("id"),
        "title": swing.get("title", ""),
        "sport": swing.get("sport", ""),
        "angle": swing.get("angle", ""),
        "benchmark_name": benchmark.get("name", "N/A") if benchmark else "N/A",
        "benchmark_id": benchmark_id,
        "target_angle": benchmark_metrics.get("spine_angle", 0),
        "current_angle": impact_metrics.get("spine_angle", 0),
        "overall_score": swing.get("overall_score", 0),
        "duration_ms": swing.get("duration_ms", 3000),
        "frames": swing.get("frames", []),
        "metrics": [
            {"label": "体幹・前傾角度", "value": f"{impact_metrics.get('spine_angle', 0):.1f}°", "benchmark": f"{benchmark_metrics.get('spine_angle', 0):.1f}°"},
            {"label": "軸ブレ幅", "value": f"+{impact_metrics.get('head_shift_x', 0):.1f} cm", "benchmark": f"+{benchmark_metrics.get('head_shift_x', 0):.1f} cm"},
            {"label": "腰の回転角", "value": f"{impact_metrics.get('hip_rotation', 0):.1f}°", "benchmark": f"{benchmark_metrics.get('hip_rotation', 0):.1f}°"},
            {"label": "肩の回転角", "value": f"{impact_metrics.get('shoulder_rotation', 0):.1f}°", "benchmark": f"{benchmark_metrics.get('shoulder_rotation', 0):.1f}°"},
        ],
    }


analysis_details = get_analysis_by_id()

form_options = {
    "sports": ["ゴルフ (Golf)", "野球 (Baseball)"],
    "angles": ["真横 (サイド)", "正面 (フロント)", "後方 (リア)"],
}
