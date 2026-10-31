from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bussola.app import create_app
from bussola.config import AppSettings
from bussola.security import allowed_hosts_for, is_local_host, token_cookie
from tests.gitrepo import GitFixture

TOKEN = "secret-token"
PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"
TOKEN_COOKIE = token_cookie(PORT)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = AppSettings(data_dir=tmp_path / "data", static_dir=tmp_path, token=TOKEN, allowed_hosts=allowed_hosts_for("127.0.0.1", PORT), port=PORT)
    return TestClient(create_app(settings), base_url=BASE_URL)


def test_api_call_without_token_is_forbidden(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 403


def test_api_call_with_wrong_token_is_forbidden(client: TestClient) -> None:
    client.cookies.set(TOKEN_COOKIE, "guess")

    assert client.get("/api/health").status_code == 403


def test_foreign_host_header_is_forbidden_even_with_token(client: TestClient) -> None:
    client.cookies.set(TOKEN_COOKIE, TOKEN)

    response = client.get("/api/health", headers={"host": f"evil.example:{PORT}"})

    assert response.status_code == 403


def test_the_session_cookie_belongs_to_one_port(client: TestClient) -> None:
    client.cookies.set("bussola_token_9000", TOKEN)

    assert client.get("/api/health").status_code == 403
    assert TOKEN_COOKIE == "bussola_token_8765"


def test_loopback_hosts_are_local() -> None:
    assert is_local_host("127.0.0.1")
    assert is_local_host("127.0.0.2")
    assert is_local_host("::1")
    assert is_local_host("localhost")
    assert not is_local_host("192.168.1.5")
    assert not is_local_host("example.com")


def test_ipv6_hosts_are_allowed_as_browsers_send_them() -> None:
    assert "[::1]:8765" in allowed_hosts_for("::1", 8765)
    assert "127.0.0.1:8765" in allowed_hosts_for("::1", 8765)
    assert "[::1]:8765" in allowed_hosts_for("::", 8765)


def test_localhost_with_the_right_port_is_allowed(client: TestClient) -> None:
    client.cookies.set(TOKEN_COOKIE, TOKEN)

    assert client.get("/api/health", headers={"host": f"localhost:{PORT}"}).status_code == 200
    assert client.get("/api/health", headers={"host": "localhost:9999"}).status_code == 403


def test_token_link_sets_a_strict_http_only_cookie_and_strips_the_token(client: TestClient) -> None:
    response = client.get(f"/reviews/3?token={TOKEN}&x=1", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/reviews/3?x=1"
    cookie = response.headers["set-cookie"]
    assert f"{TOKEN_COOKIE}={TOKEN}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert client.get("/api/health").status_code == 200


def test_option_like_refs_are_rejected_by_the_api(tmp_path: Path, git_repo: GitFixture) -> None:
    git_repo.commit({"a.txt": "a\n"})
    client = TestClient(create_app(AppSettings(data_dir=tmp_path / "data", static_dir=tmp_path, identity_dir=git_repo.root)))
    repo = client.post("/api/repos", json={"path": str(git_repo.root)}).json()

    target = tmp_path / "x"
    response = client.post(f"/api/repos/{repo['id']}/reviews", json={"head_ref": f"--output={target}", "base_ref": "main"})

    assert response.status_code == 400
    assert "Not a valid commit reference" in response.json()["detail"]
    assert not target.exists()
