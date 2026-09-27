from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from app import create_app
from app.services.analysis_job import get_analysis_by_id, list_history
from app.services.benchmark_service import list_benchmark_models
from app.services.database import dispose_database


@pytest.fixture
def app(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'guest-flow.db'}"
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


def create_account(client, username):
    client.get("/register")
    with client.session_transaction() as session:
        token = session["csrf_token"]
    response = client.post(
        "/register",
        data={
            "csrf_token": token,
            "username": username,
            "password": "guest-migration-test-password",
        },
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        return session["csrf_token"]


def test_guest_can_analyze_and_login_claims_browser_history(app):
    guest = app.test_client()
    assert guest.get("/upload").status_code == 200
    assert guest.get("/dashboard").status_code == 200
    with guest.session_transaction() as session:
        csrf = session["csrf_token"]
        guest_key = f"guest:{session['guest_id']}"

    upload = guest.post(
        "/upload",
        data={
            "csrf_token": csrf,
            "title": "guest-only swing",
            "file": (BytesIO(b"guest private video"), "guest.mp4"),
        },
        content_type="multipart/form-data",
    )
    assert upload.status_code == 302
    analysis_id = parse_qs(urlparse(upload.headers["Location"]).query)["id"][0]
    with app.app_context():
        record = get_analysis_by_id(analysis_id, owner_key=guest_key)
        assert record is not None
        assert len(list_history(owner_key=guest_key)) == 1
    video_path = Path(app.config["UPLOAD_FOLDER"]) / record["raw_video_url"].rsplit("/", 1)[1]

    assert guest.get(f"/analysis?id={analysis_id}").status_code == 200
    assert guest.get(record["video_url"]).status_code == 200

    another_guest = app.test_client()
    assert another_guest.get(f"/analysis?id={analysis_id}").status_code == 404
    assert another_guest.get(record["video_url"]).status_code == 404
    assert "ゲストで解析を始める" in another_guest.get("/").get_data(as_text=True)

    # Guest users can browse official examples but need an account to publish a private one.
    blocked = guest.post(
        "/models/new",
        data={"csrf_token": csrf, "name": "guest example"},
    )
    assert blocked.status_code == 302
    assert "/login" in blocked.headers["Location"]

    account_client = app.test_client()
    create_account(account_client, "migration-user")

    with guest.session_transaction() as session:
        csrf = session["csrf_token"]
    login = guest.post(
        "/login",
        data={
            "csrf_token": csrf,
            "username": "migration-user",
            "password": "guest-migration-test-password",
        },
    )
    assert login.status_code == 302

    with guest.session_transaction() as session:
        account_key = f"user:{session['user_id']}"
        csrf = session["csrf_token"]
    with app.app_context():
        assert get_analysis_by_id(analysis_id, owner_key=guest_key) is None
        assert get_analysis_by_id(analysis_id, owner_key=account_key) is not None

    assert guest.get(f"/analysis?id={analysis_id}").status_code == 200
    assert guest.get(record["video_url"]).status_code == 200
    with guest.session_transaction() as session:
        csrf = session["csrf_token"]
    add_private_example = guest.post(
        "/models/new",
        data={
            "csrf_token": csrf,
            "name": "account-only example",
            "file": (BytesIO(b"private benchmark video"), "example.mp4"),
        },
        content_type="multipart/form-data",
    )
    assert add_private_example.status_code == 302
    assert "account-only example" in guest.get("/models").get_data(as_text=True)
    assert "account-only example" not in another_guest.get("/models").get_data(as_text=True)
    with app.app_context():
        private_examples = list_benchmark_models(owner_key=account_key)
        assert any(model["name"] == "account-only example" for model in private_examples)

    # Logging out starts a fresh guest identity and does not expose the account's private data.
    assert guest.post("/logout", data={"csrf_token": csrf}).status_code == 302
    assert guest.get(f"/analysis?id={analysis_id}").status_code == 404
    assert video_path.exists()
