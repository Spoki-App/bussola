import getpass
from dataclasses import dataclass
from pathlib import Path

from bussola.git import read_git_config_values

FALLBACK_EMAIL_DOMAIN = "localhost"
USER_KEYS = r"^user\.(email|name)$"


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
        values = read_git_config_values(cwd, USER_KEYS)
        email = values.get("user.email") or f"{user}@{FALLBACK_EMAIL_DOMAIN}"
        name = values.get("user.name") or user
        return Identity(email, name)
