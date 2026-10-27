from pathlib import Path

from fastapi.testclient import TestClient

from rtool.app import create_app


def test_health_endpoint_reports_ok(tmp_path: Path) -> None:
    client = TestClient(create_app(static_dir=tmp_path))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_routes_fall_back_to_index(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>rtool</html>")
    client = TestClient(create_app(static_dir=tmp_path))

    response = client.get("/reviews/1")

    assert response.status_code == 200
    assert "rtool" in response.text


def test_unknown_api_route_is_not_served_as_index(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>rtool</html>")
    client = TestClient(create_app(static_dir=tmp_path))

    response = client.get("/api/missing")

    assert response.status_code == 404


def test_root_level_static_files_are_served(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>rtool</html>")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    client = TestClient(create_app(static_dir=tmp_path))

    response = client.get("/favicon.svg")

    assert response.text == "<svg/>"
