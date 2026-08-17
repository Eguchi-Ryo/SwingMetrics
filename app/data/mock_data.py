import json
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent
DATA_FILE = DATA_DIR / "swing_data.json"
DB_FILE = DATA_DIR / "swing_metrics.db"


def load_swing_data():
    """JSONファイルからスイングデータを読み込む"""
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"swings": [], "benchmark_models": []}


_swing_data = load_swing_data()


def _connect_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _seed_demo_history(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            sport TEXT NOT NULL,
            angle TEXT NOT NULL,
            model TEXT NOT NULL,
            score INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            benchmark_name TEXT,
            created_at TEXT NOT NULL,
            duration_ms INTEGER DEFAULT 3000,
            target_angle REAL DEFAULT 0,
            current_angle REAL DEFAULT 0,
            metrics TEXT DEFAULT '[]'
        )
        """
    )

    count = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    if count > 0:
        conn.commit()
        return

    default_rows = [
        (
            "7番アイアン 前傾維持チェック",
            "Golf",
            "真横 (サイド)",
            "比較モデル 1",
            82,
            "2026/08/10 14:30",
            "絶好調時の7番アイアン",
            "2026-08-10T14:30:00",
            3000,
            41.5,
            38.2,
            json.dumps([
                {"label": "体幹・前傾角度", "value": "38.2°", "benchmark": "41.5°"},
                {"label": "軸ブレ幅", "value": "+2.1 cm", "benchmark": "+1.2 cm"},
                {"label": "腰の回転角", "value": "35.0°", "benchmark": "40.0°"},
                {"label": "肩の回転角", "value": "52.0°", "benchmark": "55.0°"},
            ], ensure_ascii=False),
        ),
        (
            "フリーバッティング 踏み込み足角度",
            "Baseball",
            "正面 (フロント)",
            "比較モデル 2",
            88,
            "2026/08/05 11:15",
            "MLBクリーンナップ打者",
            "2026-08-05T11:15:00",
            2500,
            39.8,
            36.2,
            json.dumps([
                {"label": "体幹・前傾角度", "value": "36.2°", "benchmark": "39.8°"},
                {"label": "軸ブレ幅", "value": "+3.1 cm", "benchmark": "+3.0 cm"},
                {"label": "腰の回転角", "value": "40.0°", "benchmark": "42.0°"},
                {"label": "肩の回転角", "value": "52.0°", "benchmark": "55.0°"},
            ], ensure_ascii=False),
        ),
        (
            "ドライバー 軸ブレ測定",
            "Golf",
            "後方 (リア)",
            "比較モデル 1",
            75,
            "2026/07/28 16:00",
            "PGAツアープロ A",
            "2026-07-28T16:00:00",
            3200,
            42.0,
            35.4,
            json.dumps([
                {"label": "体幹・前傾角度", "value": "35.4°", "benchmark": "42.0°"},
                {"label": "軸ブレ幅", "value": "+2.4 cm", "benchmark": "+1.0 cm"},
                {"label": "腰の回転角", "value": "31.0°", "benchmark": "42.0°"},
                {"label": "肩の回転角", "value": "46.0°", "benchmark": "57.0°"},
            ], ensure_ascii=False),
        ),
    ]

    conn.executemany(
        """
        INSERT INTO analyses (
            title, sport, angle, model, score, timestamp, benchmark_name,
            created_at, duration_ms, target_angle, current_angle, metrics
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        default_rows,
    )
    conn.commit()


def init_storage():
    conn = _connect_db()
    _seed_demo_history(conn)
    conn.close()


def save_analysis(payload: dict):
    init_storage()
    conn = _connect_db()
    title = (payload.get("title") or "新規解析").strip() or "新規解析"
    sport = (payload.get("sport") or "ゴルフ (Golf)").strip() or "ゴルフ (Golf)"
    angle = (payload.get("angle") or "真横 (サイド)").strip() or "真横 (サイド)"
    model = (payload.get("model") or "比較モデル 1").strip() or "比較モデル 1"
    score = int(payload.get("score", 89))
    timestamp = payload.get("timestamp") or datetime.now().strftime("%Y/%m/%d %H:%M")
    benchmark_name = payload.get("benchmark_name") or model
    target_angle = float(payload.get("target_angle", 41.0))
    current_angle = float(payload.get("current_angle", 38.0))
    metrics = json.dumps(payload.get("metrics", []), ensure_ascii=False)

    cursor = conn.execute(
        """
        INSERT INTO analyses (
            title, sport, angle, model, score, timestamp, benchmark_name,
            created_at, duration_ms, target_angle, current_angle, metrics
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            sport,
            angle,
            model,
            score,
            timestamp,
            benchmark_name,
            datetime.now().isoformat(timespec="seconds"),
            int(payload.get("duration_ms", 3000)),
            target_angle,
            current_angle,
            metrics,
        ),
    )
    conn.commit()
    created_id = cursor.lastrowid
    conn.close()
    return get_analysis_by_id(created_id)


def list_history():
    init_storage()
    conn = _connect_db()
    rows = conn.execute(
        "SELECT * FROM analyses ORDER BY created_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "sport": row["sport"],
            "angle": row["angle"],
            "score": row["score"],
            "timestamp": row["timestamp"],
            "trend": "up" if row["score"] >= 80 else "stable",
            "benchmark_name": row["benchmark_name"],
            "model": row["model"],
            "duration_ms": row["duration_ms"],
            "target_angle": row["target_angle"],
            "current_angle": row["current_angle"],
            "metrics": json.loads(row["metrics"] or "[]"),
        }
        for row in rows
    ]


def get_analysis_by_id(swing_id: str | int | None = None):
    init_storage()
    conn = _connect_db()
    if swing_id in (None, "", "latest"):
        row = conn.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 1").fetchone()
    else:
        try:
            row = conn.execute("SELECT * FROM analyses WHERE id = ?", (int(swing_id),)).fetchone()
        except (TypeError, ValueError):
            row = conn.execute("SELECT * FROM analyses WHERE title = ?", (str(swing_id),)).fetchone()
    conn.close()

    if not row:
        return None

    metrics = json.loads(row["metrics"] or "[]")
    return {
        "id": row["id"],
        "title": row["title"],
        "sport": row["sport"],
        "angle": row["angle"],
        "benchmark_name": row["benchmark_name"],
        "benchmark_id": row["model"],
        "target_angle": row["target_angle"],
        "current_angle": row["current_angle"],
        "overall_score": row["score"],
        "duration_ms": row["duration_ms"],
        "frames": [],
        "metrics": metrics,
    }


benchmark_models = [
    {
        "id": "model_my_best",
        "name": "絶好調時の7番アイアン",
        "sport": "Golf",
        "type": "my_best",
        "angle": 41.5,
    },
    {
        "id": "model_pga_a",
        "name": "PGAツアープロ A",
        "sport": "Golf",
        "type": "pro",
        "angle": 42.0,
    },
    {
        "id": "model_mlb_cleanup",
        "name": "MLBクリーンナップ打者",
        "sport": "Baseball",
        "type": "pro",
        "angle": 39.8,
    },
]

summary_stats = {
    "total_analyses": 0,
    "average_score": 0,
    "trend_text": "前傾角度の平均ブレ幅が -1.8° 改善しています。インパクトでの起き上がり頻度が減少傾向にあります。",
}

score_history = [32, 33, 31, 35, 34, 36, 35, 37, 37.5, 38.2]

dashboard_history = list_history()
analysis_details = get_analysis_by_id("latest")

form_options = {
    "sports": ["ゴルフ (Golf)", "野球 (Baseball)"],
    "angles": ["真横 (サイド)", "正面 (フロント)", "後方 (リア)"],
}
