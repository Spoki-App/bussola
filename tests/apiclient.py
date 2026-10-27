from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from rtool.app import create_app
from rtool.config import AppSettings
from tests.gitrepo import GitFixture

type Json = Any


class ApiClient:
    def __init__(self, client: TestClient, git: GitFixture) -> None:
        self.client = client
        self.git = git

    @classmethod
    def create(cls, git: GitFixture, data_dir: Path) -> "ApiClient":
        settings = AppSettings(data_dir=data_dir, static_dir=data_dir / "static", identity_dir=git.root)
        return cls(TestClient(create_app(settings)), git)

    def call(self, method: str, url: str, expected: int = 200, body: Json = None) -> Json:
        response = self.client.request(method, f"/api{url}", json=body)
        assert response.status_code == expected, response.text
        return response.json()

    def start_review(self, head: str = "feature", base: str = "main") -> int:
        repo = self.call("POST", "/repos", 201, {"path": str(self.git.root)})
        review = self.call("POST", f"/repos/{repo['id']}/reviews", 201, {"head_ref": head, "base_ref": base})
        return review["id"]

    def refresh(self, review_id: int) -> Json:
        return self.call("POST", f"/reviews/{review_id}/refresh", body={"fetch": False})

    def units(self, review_id: int, unit_filter: str = "all") -> list[Json]:
        return self.call("GET", f"/reviews/{review_id}/units?filter={unit_filter}")

    def states(self, review_id: int, unit_filter: str = "all") -> dict[str, str]:
        return {_unit_name(unit): unit["state"] for unit in self.units(review_id, unit_filter)}

    def unit(self, review_id: int, name: str) -> Json:
        return next(unit for unit in self.units(review_id) if _unit_name(unit) == name)

    def approve(self, review_id: int, name: str) -> Json:
        return self.call("POST", f"/reviews/{review_id}/approvals", 201, {"unit_id": self.unit(review_id, name)["id"]})

    def approve_rows(self, review_id: int, name: str, head_range: tuple[int, int] | None = None, base_range: tuple[int, int] | None = None) -> Json:
        body = {"unit_id": self.unit(review_id, name)["id"], "head_range": head_range, "base_range": base_range}
        return self.call("POST", f"/reviews/{review_id}/approvals", 201, body)

    def diff(self, review_id: int, name: str, mode: str | None = None) -> Json:
        query = f"?mode={mode}" if mode else ""
        return self.call("GET", f"/reviews/{review_id}/units/{self.unit(review_id, name)['id']}/diff{query}")


def _unit_name(unit: Json) -> str:
    return f"{unit['path']}::{unit['qualified_name']}" if unit["qualified_name"] else unit["path"]


def comment_on(api: ApiClient, review_id: int, name: str, line_offset: int, body: str = "Why?") -> Json:
    payload = {"scope": "unit", "unit_id": api.unit(review_id, name)["id"], "line_offset": line_offset, "body": body}
    return api.call("POST", f"/reviews/{review_id}/threads", 201, payload)


def thread_anchor(api: ApiClient, review_id: int, thread_id: str) -> Json:
    threads = api.call("GET", f"/reviews/{review_id}/threads")
    return next(thread for thread in threads if thread["id"] == thread_id)
