from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture

OLD_PNG = b"\x89PNG\r\n\x1a\nold"
NEW_PNG = b"\x89PNG\r\n\x1a\nnew"
GIF = b"GIF89a\x01\x00"


def image_url(api: ApiClient, review: int, path: str, side: str) -> str:
    return f"/api/reviews/{review}/units/{api.unit(review, path)['id']}/image?side={side}"


def start(api: ApiClient, git_repo: GitFixture) -> int:
    git_repo.commit({"logo.png": OLD_PNG, "app.py": "x = 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"logo.png": NEW_PNG, "new.gif": GIF, "app.py": "x = 2\n"})
    return api.start_review()


def test_image_files_are_served_from_both_sides(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(api, git_repo)

    base = api.client.get(image_url(api, review, "logo.png", "base"))
    head = api.client.get(image_url(api, review, "logo.png", "head"))

    assert (base.status_code, base.content, base.headers["content-type"]) == (200, OLD_PNG, "image/png")
    assert (head.status_code, head.content) == (200, NEW_PNG)
    assert "sandbox" in head.headers["content-security-policy"]


def test_an_added_image_has_no_base_side(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(api, git_repo)

    assert api.client.get(image_url(api, review, "new.gif", "head")).content == GIF
    assert api.client.get(image_url(api, review, "new.gif", "base")).status_code == 404


def test_only_image_files_are_served(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(api, git_repo)
    unit = next(unit for unit in api.units(review) if unit["path"] == "app.py")

    response = api.client.get(f"/api/reviews/{review}/units/{unit['id']}/image?side=head")

    assert response.status_code == 400
