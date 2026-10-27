import getpass
from dataclasses import dataclass
from pathlib import Path

from rtool.git import read_git_config

FALLBACK_EMAIL_DOMAIN = "localhost"


@dataclass(frozen=True)
class Identity:
    email: str
    name: str


class GitConfigIdentity:
    def __init__(self, cwd: Path | None = None) -> None:
        self._cwd = cwd or Path.home()

    def current(self) -> Identity:
        user = getpass.getuser()
        cwd = self._cwd if self._cwd.is_dir() else Path.home()
        email = read_git_config(cwd, "user.email") or f"{user}@{FALLBACK_EMAIL_DOMAIN}"
        name = read_git_config(cwd, "user.name") or user
        return Identity(email, name)
