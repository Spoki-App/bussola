import subprocess
from collections.abc import Mapping
from pathlib import Path

from rtool.git import GitRepo

type FileContent = str | bytes | None


class GitFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.repo = GitRepo(root)

    @classmethod
    def create(cls, root: Path, default_branch: str = "main") -> "GitFixture":
        root.mkdir(parents=True, exist_ok=True)
        fixture = cls(root)
        fixture.git("init", "-q", "-b", default_branch)
        fixture.git("config", "user.email", "alice@example.com")
        fixture.git("config", "user.name", "Alice")
        fixture.git("config", "commit.gpgsign", "false")
        return fixture

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def write(self, files: Mapping[str, FileContent]) -> None:
        for path, content in files.items():
            target = self.root / path
            if content is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content)

    def commit(self, files: Mapping[str, FileContent], message: str = "change") -> str:
        self.write(files)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def branch(self, name: str, start: str = "HEAD") -> None:
        self.git("checkout", "-q", "-b", name, start)

    def checkout(self, name: str) -> None:
        self.git("checkout", "-q", name)

    def rebase(self, onto: str) -> None:
        self.git("rebase", "-q", onto)

    def move(self, source: str, target: str) -> None:
        self.git("mv", source, target)
