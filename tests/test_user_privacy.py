from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest

from app import create_app
from app.services.benchmark_service import list_benchmark_models, save_benchmark_model
from app.services.database import dispose_database


@pytest.fixture
def app(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'privacy.db'}"
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
    monkeypatch.setattr("app.services.analysis_job._run_yolo_task", lambda *args: None)
    monkeypatch.setattr("app.routes.main.start_benchmark_analysis", lambda *args: None)
    yield app
    dispose_database(database_url)


def register(client, username):
    assert client.get("/register").status_code == 200
    with client.session_transaction() as session:
        token = session["csrf_token"]
    response = client.post(
        "/register",
        data={
            "csrf_token": token,
            "username": username,
            "password": "user-test-password-123",
        },
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        return session["user_id"], session["csrf_token"]


def test_users_only_see_their_own_examples_analyses_and_videos(app):
    first = app.test_client()
    first_user_id, first_csrf = register(first, "first-user")

    own_analysis = first.post(
        "/upload",
        data={
            "csrf_token": first_csrf,
            "title": "first user's private analysis",
            "file": (BytesIO(b"private analysis video"), "analysis.mp4"),
        },
        content_type="multipart/form-data",
    )
    assert own_analysis.status_code == 302
    analysis_id = parse_qs(urlparse(own_analysis.headers["Location"]).query)["id"][0]
    private_video_path = next(Path(app.config["UPLOAD_FOLDER"]).glob("batting_*.mp4"))
    private_video_url = f"/videos/{private_video_path.name}"

    private_model = first.post(
        "/models/new",
        data={
            "csrf_token": first_csrf,
            "name": "first private example",
            "file": (BytesIO(b"private example video"), "example.mp4"),
        },
        content_type="multipart/form-data",
    )
    assert private_model.status_code == 302

    with app.app_context():
        first_models = list_benchmark_models(owner_key=f"user:{first_user_id}")
        private_model_data = next(model for model in first_models if not model.get("is_official"))
    private_example_path = Path(app.config["UPLOAD_FOLDER"]) / private_model_data["raw_video_url"].rsplit("/", 1)[1]

    official_path = Path(app.config["UPLOAD_FOLDER"]) / "official-shared.mp4"
    official_path.write_bytes(b"public official video")
    with app.app_context():
        save_benchmark_model(
            {
                "name": "public official example",
                "sport": "Baseball",
                "angle": "Side",
                "video_url": "/videos/official-shared.mp4",
                "raw_video_url": "/videos/official-shared.mp4",
                "target_angle": 10.0,
                "frames": [],
                "metrics": [],
                "status": "completed",
                "owner_id": None,
                "is_official": True,
            }
        )

    second = app.test_client()
    second_user_id, second_csrf = register(second, "second-user")
    second_library = second.get("/models").get_data(as_text=True)
    assert "public official example" in second_library
    assert "first private example" not in second_library
    assert second.get("/api/models").json
    assert all(model.get("is_official") for model in second.get("/api/models").json)
    assert second.get(private_video_url).status_code == 404
    assert second.get(private_model_data["raw_video_url"]).status_code == 404
    assert second.get("/videos/official-shared.mp4").status_code == 200
    assert second.get(f"/analysis?id={analysis_id}").status_code == 404
    assert second.get("/api/jobs/1").status_code == 404
    assert "first private analysis" not in second.get("/dashboard").get_data(as_text=True)
    denied_analysis_delete = second.post(
        f"/api/analysis/{analysis_id}/delete",
        headers={"X-CSRFToken": second_csrf},
    )
    assert denied_analysis_delete.status_code == 404
    assert private_video_path.exists()

    assert first.get(private_video_url).status_code == 200
    assert first.get(private_model_data["raw_video_url"]).status_code == 200
    assert first.get(f"/analysis?id={analysis_id}").status_code == 200

    own_analysis_delete = first.post(
        f"/api/analysis/{analysis_id}/delete",
        headers={"X-CSRFToken": first_csrf},
    )
    assert own_analysis_delete.status_code == 200
    assert not private_video_path.exists()

    visitor = app.test_client()
    public_library = visitor.get("/models").get_data(as_text=True)
    assert "public official example" in public_library
    assert "first private example" not in public_library
    assert visitor.get("/videos/official-shared.mp4").status_code == 200
    assert visitor.get(private_model_data["video_url"]).status_code == 404

    denied_delete = second.post(
        f"/api/models/{private_model_data['id']}/delete",
        headers={"X-CSRFToken": second_csrf},
    )
    assert denied_delete.status_code == 404
    assert private_example_path.exists()

    own_delete = first.post(
        f"/api/models/{private_model_data['id']}/delete",
        headers={"X-CSRFToken": first_csrf},
    )
    assert own_delete.status_code == 200
    assert not private_example_path.exists()
