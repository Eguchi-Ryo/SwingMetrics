from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import create_app
from app.services.benchmark_service import list_benchmark_models, save_benchmark_model
from app.services.database import dispose_database


@pytest.fixture
def app(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'benchmark-test.db'}"
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": database_url,
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "ADMIN_USERNAME": "test-admin",
            "ADMIN_PASSWORD": "test-password",
            "ADMIN_LOGIN_PATH": "/management-console-7f31a9c2b84e6d0a5f42",
        }
    )

    import app.services.benchmark_service as benchmark_service

    def fake_video_analysis(video_path, output_dir, progress_callback=None):
        annotated_path = Path(output_dir) / f"annotated_{Path(video_path).name}"
        annotated_path.write_bytes(b"annotated skeleton video")
        if progress_callback:
            progress_callback(100)
        return {
            "annotated_video_url": f"/videos/{annotated_path.name}",
            "attack_angle": 12.5,
            "overall_score": 90,
            "metrics": [],
            "frames": [
                {"frame_index": 0, "spine_angle": 31.0},
                {"frame_index": 1, "spine_angle": 34.5},
            ],
        }

    class ImmediateThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(benchmark_service, "analyze_batting_video", fake_video_analysis)
    monkeypatch.setattr(benchmark_service, "threading", SimpleNamespace(Thread=ImmediateThread))
    yield app
    dispose_database(database_url)


def test_public_can_view_benchmarks_but_cannot_manage_them(app):
    upload_dir = app.config["UPLOAD_FOLDER"]
    Path(upload_dir).mkdir(parents=True, exist_ok=True)
    (Path(upload_dir) / "shared.mp4").write_bytes(b"shared video")
    with app.app_context():
        save_benchmark_model(
            {
                "name": "共有お手本",
                "sport": "野球 (打撃)",
                "angle": "真横",
                "video_url": "/videos/shared.mp4",
                "target_angle": 10.0,
                "frames": [],
                "is_official": True,
            }
        )

    with app.test_client() as client:
        response = client.get("/models")
        assert response.status_code == 200
        assert "共有お手本" in response.get_data(as_text=True)
        assert "お手本動画を追加" not in response.get_data(as_text=True)
        assert "管理者ログイン" not in response.get_data(as_text=True)
        assert app.config["ADMIN_LOGIN_PATH"] not in response.get_data(as_text=True)
        assert client.get("/admin/login").status_code == 404

        forbidden = client.post(
            "/models/new",
            data={"name": "unauthorized", "file": (BytesIO(b"video"), "x.mp4")},
            content_type="multipart/form-data",
        )
        assert forbidden.status_code == 403


def test_admin_can_log_in_add_and_delete_benchmark(app):
    with app.test_client() as client:
        login_path = app.config["ADMIN_LOGIN_PATH"]
        login_page = client.get(login_path)
        assert login_page.status_code == 200
        with client.session_transaction() as session:
            csrf = session["csrf_token"]

        login = client.post(
            login_path,
            data={
                "csrf_token": csrf,
                "username": "test-admin",
                "password": "test-password",
            },
        )
        assert login.status_code == 302
        with client.session_transaction() as session:
            csrf = session["csrf_token"]

        added = client.post(
            "/models/new",
            data={
                "csrf_token": csrf,
                "name": "管理者登録動画",
                "file": (BytesIO(b"example video"), "example.mp4"),
            },
            content_type="multipart/form-data",
        )
        assert added.status_code == 302

        with app.app_context():
            model = list_benchmark_models()[0]
        assert model["status"] == "completed"
        assert "angle" not in model
        assert model["target_angle"] == 12.5
        assert model["frames"] == [
            {"frame_index": 0, "spine_angle": 31.0},
            {"frame_index": 1, "spine_angle": 34.5},
        ]
        assert model["video_url"].endswith("annotated_" + model["raw_video_url"].rsplit("/", 1)[1])
        saved_video = Path(app.config["UPLOAD_FOLDER"]) / model["video_url"].rsplit("/", 1)[1]
        assert saved_video.exists()

        library = client.get("/models")
        assert "管理者登録動画" in library.get_data(as_text=True)
        assert "撮影アングル" not in library.get_data(as_text=True)
        deleted = client.post(
            f"/api/models/{model['id']}/delete",
            headers={"X-CSRFToken": csrf},
        )
        assert deleted.status_code == 200
        assert deleted.json["success"] is True
        assert not saved_video.exists()

        with app.app_context():
            assert list_benchmark_models() == []


def test_admin_login_rejects_wrong_password(app):
    with app.test_client() as client:
        login_path = app.config["ADMIN_LOGIN_PATH"]
        client.get(login_path)
        with client.session_transaction() as session:
            csrf = session["csrf_token"]
        response = client.post(
            login_path,
            data={"csrf_token": csrf, "username": "test-admin", "password": "wrong"},
        )
        assert response.status_code == 200
        assert "正しくありません" in response.get_data(as_text=True)


def test_admin_login_route_is_not_registered_without_private_path(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'no-admin.db'}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "ADMIN_USERNAME": "",
            "ADMIN_PASSWORD": "",
            "ADMIN_LOGIN_PATH": "",
        }
    )
    with app.test_client() as client:
        assert client.get("/admin/login").status_code == 404
        assert "管理者ログイン" not in client.get("/").get_data(as_text=True)