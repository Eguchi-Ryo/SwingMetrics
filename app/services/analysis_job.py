import json
import threading
import time
from pathlib import Path
from app.services.yolo_service import analyze_batting_video

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_ROOT / "data" / "jobs.json"
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

def _load_jobs():
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_jobs(jobs):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

def list_history():
    return sorted(_load_jobs(), key=lambda x: x.get("id", 0), reverse=True)

def get_analysis_by_id(job_id):
    jobs = _load_jobs()
    if job_id == "latest":
        return jobs[-1] if jobs else None
    try:
        jid = int(job_id)
        return next((j for j in jobs if j.get("id") == jid), None)
    except Exception:
        return None

def delete_analysis_by_id(job_id):
    jobs = _load_jobs()
    try:
        jid = int(job_id)
        jobs = [j for j in jobs if j.get("id") != jid]
        _save_jobs(jobs)
        return True
    except Exception:
        return False

def _run_yolo_task(job_id, video_filename):
    """別スレッドでYOLO解析を実行"""
    def update_progress(p):
        jobs = _load_jobs()
        for j in jobs:
            if j.get("id") == job_id:
                j["progress"] = p
                break
        _save_jobs(jobs)

    video_path = UPLOAD_DIR / video_filename
    try:
        result = analyze_batting_video(video_path, output_dir=UPLOAD_DIR, progress_callback=update_progress)
        
        jobs = _load_jobs()
        for j in jobs:
            if j.get("id") == job_id:
                j["status"] = "completed"
                j["progress"] = 100
                j["annotated_video_url"] = result["annotated_video_url"]
                j["video_url"] = result["annotated_video_url"] # 骨格描画版を再生用URLに
                j["current_angle"] = result["attack_angle"]
                j["overall_score"] = result["overall_score"]
                j["score"] = result["overall_score"]
                j["metrics"] = result["metrics"]
                j["frames"] = result["frames"]
                break
        _save_jobs(jobs)
    except Exception as e:
        print(f"YOLO analysis error for job {job_id}: {e}")
        jobs = _load_jobs()
        for j in jobs:
            if j.get("id") == job_id:
                j["status"] = "error"
                j["error_msg"] = str(e)
                break
        _save_jobs(jobs)

def save_analysis(payload):
    jobs = _load_jobs()
    new_id = (max([j.get("id", 0) for j in jobs]) + 1) if jobs else 1
    video_url = payload.get("video_url", "")
    filename = Path(video_url).name if video_url else ""

    job = {
        "id": new_id,
        "title": payload.get("title", "打撃スイング解析"),
        "sport": "野球 (打撃)",
        "angle": payload.get("angle", "真横 (打者正面側 / サイド)"),
        "status": "processing" if filename else "completed",
        "progress": 0,
        "video_url": video_url,
        "annotated_video_url": "",
        "current_angle": 0.0,
        "overall_score": 0,
        "metrics": [],
        "frames": [],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    jobs.append(job)
    _save_jobs(jobs)

    # 実際の動画ファイルが存在する場合、YOLOスレッドを起動
    if filename:
        t = threading.Thread(target=_run_yolo_task, args=(new_id, filename), daemon=True)
        t.start()

    return job