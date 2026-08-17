from app import create_app


def test_analysis_route_uses_uploaded_values():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        resp = client.get(
            "/analysis?title=野球スイング%20軸確認&sport=野球%20(Baseball)&angle=正面%20(フロント)"
        )

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "野球スイング 軸確認" in html
        assert "野球 (Baseball)" in html
        assert "正面 (フロント)" in html


def test_dashboard_includes_latest_uploaded_analysis():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        client.get(
            "/analysis?title=野球スイング%20軸確認&sport=野球%20(Baseball)&angle=正面%20(フロント)"
        )
        resp = client.get("/dashboard")

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "野球スイング 軸確認" in html
