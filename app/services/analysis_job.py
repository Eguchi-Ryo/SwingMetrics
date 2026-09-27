import threading
import time
from pathlib import Path

from flask import current_app, has_app_context

from app.services.database import (
    AnalysisJob,
    build_database_url,
    get_session_factory,
    payload_belongs_to_owner,
)
from app.services.yolo_service import analyze_batting_video


def _database_url(database_url=None):
    if database_url:
        return database_url
    if has_app_context():
        return current_app.config["DATABASE_URL"]
    return build_database_url()


def _upload_dir(upload_dir=None):
    if upload_dir:
        return Path(upload_dir)
    if has_app_context():
        return Path(current_app.config["UPLOAD_FOLDER"])
    return Path(__file__).resolve().parents[2] / "data" / "uploads"


def list_history(owner_key=None, database_url=None):
    if owner_key is None:
        return []
    session_factory = get_session_factory(_database_url(database_url))
    with session_factory() as session:
        rows = session.query(AnalysisJob).order_by(AnalysisJob.id.desc()).all()
        return [dict(row.payload) for row in rows if payload_belongs_to_owner(row.payload, owner_key)]


def get_analysis_by_id(job_id, owner_key=None, database_url=None):
    if owner_key is None:
        return None
    session_factory = get_session_factory(_database_url(database_url))
    with session_factory() as session:
        if job_id == "latest":
            rows = session.query(AnalysisJob).order_by(AnalysisJob.id.desc()).all()
            row = next(
                (item for item in rows if payload_belongs_to_owner(item.payload, owner_key)),
                None,
            )
        else:
            try:
                row = session.get(AnalysisJob, int(job_id))
            except (TypeError, ValueError):
                return None
        if row is None or not payload_belongs_to_owner(row.payload, owner_key):
            return None
        return dict(row.payload)


def update_analysis(job_id, changes, database_url=None):
    session_factory = get_session_factory(_database_url(database_url))
    with session_factory.begin() as session:
        row = session.get(AnalysisJob, int(job_id))
        if row is None:
            return False
        row.payload = {**row.payload, **changes}
        return True


def delete_analysis_by_id(job_id, owner_key=None, database_url=None):
    if owner_key is None:
        return False
    session_factory = get_session_factory(_database_url(database_url))
    try:
        analysis_id = int(job_id)
    except (TypeError, ValueError):
        return False

    with session_factory.begin() as session:
        row = session.get(AnalysisJob, analysis_id)
        if row is None or not payload_belongs_to_owner(row.payload, owner_key):
            return False
        session.delete(row)
    return True


def can_view_analysis_video(filename, owner_key=None, database_url=None):
    if owner_key is None:
        return False
    session_factory = get_session_factory(_database_url(database_url))
    with session_factory() as session:
        rows = session.query(AnalysisJob).all()
        for row in rows:
            payload = row.payload
            if not payload_belongs_to_owner(payload, owner_key):
                continue
            urls = (
                payload.get("video_url"),
                payload.get("raw_video_url"),
                payload.get("annotated_video_url"),
            )
            if any(url and Path(url).name == filename for url in urls):
                return True
    return False


def _run_yolo_task(job_id, video_filename, database_url, upload_dir, on_complete=None):
    """別スレッドでYOLO解析を実行し、進捗と結果をDBへ保存する。"""
    def update_progress(progress):
        update_analysis(job_id, {"progress": progress}, database_url)

    video_path = Path(upload_dir) / video_filename
    try:
        result = analyze_batting_video(
            video_path,
            output_dir=upload_dir,
            progress_callback=update_progress,
        )
        update_analysis(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "annotated_video_url": result["annotated_video_url"],
                "video_url": result["annotated_video_url"],
                "current_angle": result["attack_angle"],
                "overall_score": result["overall_score"],
                "score": result["overall_score"],
                "metrics": result["metrics"],
                "frames": result["frames"],
            },
            database_url,
        )
        if on_complete:
            on_complete(result, None)
    except Exception as error:
        print(f"YOLO analysis error for job {job_id}: {error}")
        update_analysis(
            job_id,
            {"status": "error", "error_msg": str(error)},
            database_url,
        )
        if on_complete:
            on_complete(None, str(error))


def save_analysis(payload, database_url=None, upload_dir=None, on_complete=None, owner_key=None):
    database_url = _database_url(database_url)
    upload_dir = _upload_dir(upload_dir)
    video_url = payload.get("video_url", "")
    filename = Path(video_url).name if video_url else ""
    job_payload = {
        "title": payload.get("title", "打撃スイング解析"),
        "sport": payload.get("sport", "野球 (打撃)"),
        "angle": payload.get("angle", "真横 (打者正面側 / サイド)"),
        "status": "processing" if filename else "completed",
        "progress": 0,
        "video_url": video_url,
        "raw_video_url": video_url,
        "annotated_video_url": "",
        "current_angle": 0.0,
        "overall_score": 0,
        "metrics": [],
        "frames": [],
        "owner_key": owner_key,
        "owner_id": (
            int(owner_key.partition(":")[2])
            if owner_key and owner_key.startswith("user:")
            else None
        ),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    session_factory = get_session_factory(database_url)
    with session_factory.begin() as session:
        row = AnalysisJob(payload=job_payload)
        session.add(row)
        session.flush()
        row.payload = {**job_payload, "id": row.id}
        job = dict(row.payload)

    if filename:
        thread = threading.Thread(
            target=_run_yolo_task,
            args=(job["id"], filename, database_url, str(upload_dir), on_complete),
            daemon=True,
        )
        thread.start()

    return job
