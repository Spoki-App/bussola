import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
STATIC_DIR = Path(__file__).parent / "static"
REPO_CONFIG_FILE = ".bussola.toml"
DEFAULT_BASE_CANDIDATES = ("develop", "main", "master")
DEFAULT_FILE_LEVEL = ("**/migrations/*.py", "*.lock", "package-lock.json", "pnpm-lock.yaml", "*.min.js")


class RepoConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base_branch: str | None = None
    file_level: tuple[str, ...] = DEFAULT_FILE_LEVEL
    ignore: tuple[str, ...] = ()


def load_repo_config(root: Path) -> RepoConfig:
    path = root / REPO_CONFIG_FILE
    if not path.is_file():
        return RepoConfig()
    return RepoConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class AppSettings:
    data_dir: Path
    static_dir: Path = STATIC_DIR
    identity_dir: Path | None = None
    token: str | None = None
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
