from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import create_app
from app.services.database import dispose_database


@pytest.fixture
def app(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": database_url,
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "ADMIN_USERNAME": "",
            "ADMIN_PASSWORD": "",
            "ADMIN_LOGIN_PATH": "",
        }
    )

    # Keep upload route tests independent from model inference and its runtime cost.
    monkeypatch.setattr("app.services.analysis_job._run_yolo_task", lambda *args: None)
    yield app
    dispose_database(database_url)


def register_test_user(client, username="test-user"):
    assert client.get("/register").status_code == 200
    with client.session_transaction() as session:
        csrf = session["csrf_token"]
    response = client.post(
        "/register",
        data={
            "csrf_token": csrf,
            "username": username,
            "password": "strong-test-password-123",
        },
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        return session["user_id"], session["csrf_token"]


def test_uploaded_video_and_analysis_are_persisted(app):
    with app.test_client() as client:
        owner_id, csrf = register_test_user(client)
        response = client.post(
            "/upload",
            data={
                "csrf_token": csrf,
                "title": "野球スイング 軸確認",
                "file": (BytesIO(b"fake video bytes"), "swing.mp4"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "野球スイング 軸確認" in html

        with app.test_request_context():
            from app.services.analysis_job import get_analysis_by_id, list_history

            owner_key = f"user:{owner_id}"
            history = list_history(owner_key=owner_key)
            saved = get_analysis_by_id(history[0]["id"], owner_key=owner_key)

        assert saved["title"] == "野球スイング 軸確認"
        assert saved["status"] == "processing"
        assert "angle" not in saved
        stored_video = app.config["UPLOAD_FOLDER"] + "/" + saved["video_url"].rsplit("/", 1)[1]
        with open(stored_video, "rb") as video:
            assert video.read() == b"fake video bytes"

        video_response = client.get(saved["video_url"])
        assert video_response.status_code == 200
        assert video_response.data == b"fake video bytes"


def test_upload_without_file_is_rejected(app):
    with app.test_client() as client:
        _, csrf = register_test_user(client)
        upload_page = client.get("/upload").get_data(as_text=True)
        assert "撮影画角" not in upload_page
        response = client.post(
            "/upload", data={"csrf_token": csrf, "title": "empty"}
        )
        assert response.status_code == 400


def test_analysis_memo_is_persisted_and_score_and_direction_are_absent(app):
    with app.test_client() as client:
        _, csrf = register_test_user(client)
        upload = client.post(
            "/upload",
            data={
                "csrf_token": csrf,
                "file": (BytesIO(b"fake video bytes"), "swing.mp4"),
            },
            content_type="multipart/form-data",
        )
        assert upload.status_code == 302
        analysis_id = upload.headers["Location"].rsplit("=", 1)[1]

        saved = client.post(
            f"/api/analysis/{analysis_id}/memo",
            json={"memo": "次回は軸を意識する"},
            headers={"X-CSRFToken": csrf},
        )
        assert saved.status_code == 200
        assert saved.json["memo"] == "次回は軸を意識する"

        page = client.get(f"/analysis?id={analysis_id}")
        html = page.get_data(as_text=True)
        assert "次回は軸を意識する" in html
        assert "Batting Quality Score" not in html
        assert "Attack Direction" not in html
        assert client.get("/images/spine_angle.png").status_code == 200


def test_upload_trims_video_before_analysis(app, monkeypatch):
    def fake_ffmpeg(args, **kwargs):
        if args[0] == "ffprobe":
            return SimpleNamespace(stdout="8.0")
        Path(args[-1]).write_bytes(b"trimmed video bytes")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr("app.routes.main.subprocess.run", fake_ffmpeg)
    with app.test_client() as client:
        owner_id, csrf = register_test_user(client)
        response = client.post(
            "/upload",
            data={
                "csrf_token": csrf,
                "trim_start": "2.0",
                "trim_end": "5.0",
                "file": (BytesIO(b"full video bytes"), "swing.mov"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 302
        analysis_id = response.headers["Location"].rsplit("=", 1)[1]

        with app.test_request_context():
            from app.services.analysis_job import get_analysis_by_id

            saved = get_analysis_by_id(analysis_id, owner_key=f"user:{owner_id}")

        trimmed_path = Path(app.config["UPLOAD_FOLDER"]) / saved["raw_video_url"].rsplit("/", 1)[1]
        assert trimmed_path.name.endswith("_trimmed.mp4")
        assert trimmed_path.read_bytes() == b"trimmed video bytes"
        assert len(list(Path(app.config["UPLOAD_FOLDER"]).glob("batting_*.mov"))) == 0
