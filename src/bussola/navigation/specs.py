from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ServerSpec:
    family: str
    language: str
    commands: tuple[tuple[str, ...], ...]
    install: str
    language_ids: dict[str, str] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    initialization_options: dict[str, Any] = field(default_factory=dict)


SERVER_SPECS: dict[str, ServerSpec] = {
    "python": ServerSpec(
        "python",
        "Python",
        (("basedpyright-langserver", "--stdio"), ("pyright-langserver", "--stdio")),
        "uv tool install basedpyright",
        {".py": "python", ".pyi": "python"},
    ),
    "ecmascript": ServerSpec(
        "ecmascript",
        "TypeScript and JavaScript",
        (("typescript-language-server", "--stdio"),),
        "npm install -g typescript-language-server typescript",
        {".ts": "typescript", ".tsx": "typescriptreact", ".js": "javascript", ".jsx": "javascriptreact", ".mjs": "javascript", ".cjs": "javascript"},
        initialization_options={"disableAutomaticTypingAcquisition": True},
    ),
    "go": ServerSpec("go", "Go", (("gopls",),), "go install golang.org/x/tools/gopls@latest", {".go": "go"}, {"GOPROXY": "off", "GOTOOLCHAIN": "local"}),
}
