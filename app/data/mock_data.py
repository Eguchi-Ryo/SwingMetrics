benchmark_models = [
    {
        "id": "bm_baseball_level",
        "name": "【公式】プロ基準 レベル〜アッパー打撃フォーム",
        "sport": "野球 (打撃)",
        "angle": "真横 (サイド)",
        "target_angle": 10.0,
        "video_url": "/videos/official_baseball_side.mp4",
        "frames": [{"frame_index": i, "spine_angle": round(36.0 + i * 0.2, 1)} for i in range(30)],
        "is_system": True,
    }
]

form_options = {
    "angles": ["真横 (打者正面側 / サイド)", "後方 (捕手・審判視点)", "正面 (投手視点)"],
    "batting_types": ["右打者 (Right)", "左打者 (Left)"],
    "sports": ["野球 (打撃)"],
}

summary_stats = {
    "trend_text": "バッティング動画をアップロードして打撃幾何学データを解析しましょう。"
}

score_history = []