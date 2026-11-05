import os
import subprocess
import sys
from pathlib import Path

from bussola.config import DATA_DIR_ENV

HEAVY_MODULES = ("alembic", "fastapi", "sqlalchemy", "uvicorn", "bussola.app", "bussola.storage.models")
LOADED = (
    "import runpy, sys\n"
    "sys.argv = ['bussola', 'open-link', '--help']\n"
    "try:\n"
    "    runpy.run_module('bussola', run_name='__main__')\n"
    "except SystemExit:\n"
    "    pass\n"
    f"print(sorted(name for name in {HEAVY_MODULES!r} if name in sys.modules))\n"
)


def run_bussola(*arguments: str, data_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-P", *arguments], capture_output=True, text=True, env={**os.environ, DATA_DIR_ENV: str(data_dir)}, check=False)


def test_opening_a_link_loads_none_of_the_web_server(tmp_path: Path) -> None:
    result = run_bussola("-c", LOADED, data_dir=tmp_path)

    assert result.stdout.strip().splitlines()[-1] == "[]"


def test_python_m_bussola_open_link_refuses_an_invalid_link_and_logs_why(tmp_path: Path) -> None:
    result = run_bussola("-m", "bussola", "open-link", "--", "bussola://review?repo=acme/widgets", data_dir=tmp_path)

    assert result.returncode == 2
    assert "pr parameter" in result.stderr
    assert "The pr parameter must be a positive number" in (tmp_path / "open-link.log").read_text()
