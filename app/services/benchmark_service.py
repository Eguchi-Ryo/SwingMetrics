import threading
from pathlib import Path

from flask import current_app, has_app_context

from app.services.database import (
    BenchmarkModel,
    build_database_url,
    get_session_factory,
    payload_belongs_to_owner,
)
from app.services.yolo_service import analyze_batting_video


def _is_public_official(payload):
    # Rows created before owner scopes existed came only from the admin-only route.
    return payload.get("is_official") is True or (
        "is_official" not in payload and "owner_id" not in payload
    )


def _database_url(database_url=None):
    if database_url:
        return database_url
    if has_app_context():
        return current_app.config["DATABASE_URL"]
    return build_database_url()


def list_benchmark_models(owner_key=None, database_url=None):
    session_factory = get_session_factory(_database_url(database_url))
    with session_factory() as session:
        rows = session.query(BenchmarkModel).order_by(BenchmarkModel.id.desc()).all()
        visible_models = []
        for row in rows:
            payload = dict(row.payload)
            is_official = _is_public_official(payload)
            if is_official:
                payload["is_official"] = True
            if is_official or (
                owner_key is not None and payload_belongs_to_owner(payload, owner_key)
            ):
                visible_models.append(payload)
        return visible_models


def save_benchmark_model(payload, database_url=None):
    session_factory = get_session_factory(_database_url(database_url))
    with session_factory.begin() as session:
        row = BenchmarkModel(payload=dict(payload))
        session.add(row)
        session.flush()
        row.payload = {**payload, "id": str(row.id)}
        return dict(row.payload)


def update_benchmark_model(model_id, changes, database_url=None):
    try:
        model_id = int(model_id)
    except (TypeError, ValueError):
        return False

    session_factory = get_session_factory(_database_url(database_url))
    with session_factory.begin() as session:
        row = session.get(BenchmarkModel, model_id)
        if row is None:
            return False
        row.payload = {**row.payload, **changes}
        return True


def _run_benchmark_analysis(model_id, filename, upload_dir, database_url):
    def update_progress(progress):
        update_benchmark_model(model_id, {"progress": progress}, database_url)

    try:
        result = analyze_batting_video(
            Path(upload_dir) / filename,
            output_dir=upload_dir,
            progress_callback=update_progress,
        )
        update_benchmark_model(
            model_id,
            {
                "status": "completed",
                "progress": 100,
                "video_url": result["annotated_video_url"],
                "target_angle": float(result.get("attack_angle") or 0.0),
                "frames": result.get("frames") or [],
                "metrics": result.get("metrics") or [],
            },
            database_url,
        )
    except Exception as error:
        update_benchmark_model(
            model_id,
            {"status": "error", "error_msg": str(error)},
            database_url,
        )


def start_benchmark_analysis(model_id, filename, upload_dir, database_url=None):
    database_url = _database_url(database_url)
    thread = threading.Thread(
        target=_run_benchmark_analysis,
        args=(model_id, filename, str(upload_dir), database_url),
        daemon=True,
    )
    thread.start()


def delete_benchmark_model(model_id, owner_key=None, is_admin=False, database_url=None):
    try:
        model_id = int(model_id)
    except (TypeError, ValueError):
        return None

    session_factory = get_session_factory(_database_url(database_url))
    with session_factory.begin() as session:
        row = session.get(BenchmarkModel, model_id)
        if row is None:
            return None
        payload = dict(row.payload)
        is_owner = owner_key is not None and payload_belongs_to_owner(payload, owner_key)
        is_manageable_official = is_admin and _is_public_official(payload)
        if not (is_owner or is_manageable_official):
            return None
        session.delete(row)
        return payload


def can_view_benchmark_video(filename, owner_key=None, database_url=None):
    session_factory = get_session_factory(_database_url(database_url))
    with session_factory() as session:
        rows = session.query(BenchmarkModel).all()
        for row in rows:
            payload = row.payload
            is_visible = _is_public_official(payload) or (
                owner_key is not None and payload_belongs_to_owner(payload, owner_key)
            )
            if not is_visible:
                continue
            urls = (payload.get("video_url"), payload.get("raw_video_url"))
            if any(url and url.rsplit("/", 1)[-1] == filename for url in urls):
                return True
    return False
