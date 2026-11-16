import pytest

from tests.apiclient import ApiClient
from tests.gitrepo import FileContent, GitFixture


def _line_length(api: ApiClient, git_repo: GitFixture, files: dict[str, FileContent]) -> tuple[int, str | None]:
    git_repo.commit({"app.py": "x = 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "x = 2\n", **files})
    found = api.call("GET", f"/reviews/{api.start_review()}/line-length")
    return found["columns"], found["source"]


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({".editorconfig": "root = true\n\n[*]\nindent_style = space\nmax_line_length = 100\n"}, (100, ".editorconfig")),
        ({".editorconfig": "[*.md]\nmax_line_length = off\n\n[*.py]\nmax_line_length = 99 ; python\n"}, (99, ".editorconfig")),
        ({".editorconfig": "[*.py]\nmax_line_length = 88\n\n[*]\nmax_line_length = 110\n"}, (110, ".editorconfig")),
        ({"pyproject.toml": "[tool.ruff]\nline-length = 130\n\n[tool.black]\nline-length = 88\n"}, (130, "pyproject.toml ruff")),
        ({"pyproject.toml": "[tool.black]\nline-length = 88\n"}, (88, "pyproject.toml black")),
        ({"ruff.toml": "line-length = 140\n", "pyproject.toml": "[tool.ruff]\nline-length = 90\n"}, (140, "ruff.toml")),
        ({".ruff.toml": "line-length = 150\n", "ruff.toml": "line-length = 140\n"}, (150, ".ruff.toml")),
        ({".prettierrc": '{ "semi": false, "printWidth": 160 }\n'}, (160, ".prettierrc")),
        ({"pyproject.toml": '[tool.ruff]\nselect = ["E"]\n\n[tool.black]\nline-length = 100\n'}, (88, "pyproject.toml ruff")),
        ({"ruff.toml": '[lint]\nselect = ["E"]\n'}, (88, "ruff.toml")),
        ({".prettierrc": '{"overrides": [{"files": "*.md", "options": {"printWidth": 80}}], "printWidth": 120}'}, (120, ".prettierrc")),
        ({".prettierrc": "# printWidth: 100\noverrides:\n  - files: '*.md'\n    options:\n      printWidth: 80\nprintWidth: 140\n"}, (140, ".prettierrc")),
        ({".prettierrc.yaml": "semi: false\nprintWidth: 100\n"}, (100, ".prettierrc.yaml")),
        ({".prettierrc.toml": "printWidth = 90\n"}, (90, ".prettierrc.toml")),
        ({"package.json": '{"name": "web", "prettier": {"printWidth": 110}}\n'}, (110, "package.json prettier")),
        ({".editorconfig": "[*]\nmax_line_length = 100\n", "pyproject.toml": "[tool.ruff]\nline-length = 130\n"}, (100, ".editorconfig")),
        ({"pyproject.toml": "[tool.ruff]\nline-length = 130\n", ".prettierrc": '{"printWidth": 80}'}, (130, "pyproject.toml ruff")),
    ],
)
def test_line_length_is_read_from_the_repository(api: ApiClient, git_repo: GitFixture, files: dict[str, FileContent], expected: tuple[int, str]) -> None:
    assert _line_length(api, git_repo, files) == expected


@pytest.mark.parametrize(
    "files",
    [
        {},
        {".editorconfig": "[*]\nmax_line_length = off\n"},
        {"pyproject.toml": "[tool.ruff\nline-length = 100\n"},
        {"pyproject.toml": "[tool.ruff]\nline-length = 5000\n"},
        {"pyproject.toml": "[tool.isort]\nline_length = 100\n"},
        {"package.json": '{"prettier": "@company/prettier-config"}'},
        {"package.json": "not json"},
        {".prettierrc": '{"overrides": [{"files": "*.md", "options": {"printWidth": 80}}]}'},
    ],
)
def test_line_length_falls_back_to_120(api: ApiClient, git_repo: GitFixture, files: dict[str, FileContent]) -> None:
    assert _line_length(api, git_repo, files) == (120, None)


def test_line_length_is_read_at_the_reviewed_head(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"app.py": "x = 1\n", "pyproject.toml": "[tool.ruff]\nline-length = 88\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "x = 2\n", "pyproject.toml": "[tool.ruff]\nline-length = 100\n"})
    git_repo.write({"pyproject.toml": "[tool.ruff]\nline-length = 79\n"})

    found = api.call("GET", f"/reviews/{api.start_review()}/line-length")

    assert found == {"columns": 100, "source": "pyproject.toml ruff"}
