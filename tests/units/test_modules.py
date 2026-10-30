import pytest

from bussola.units.modules import go_module_name, module_path

GO_MODULES = {"": "example.com/shop", "tools/lint": "example.com/lint"}


def no_go_module(_directory: str) -> None:
    return None


@pytest.mark.parametrize(
    ("path", "module"),
    [
        ("src/bussola/review/anchoring.py", "bussola.review.anchoring"),
        ("src/bussola/__init__.py", "bussola"),
        ("tests/units/helpers.py", "tests.units.helpers"),
        ("app.py", "app"),
        ("stubs/types.pyi", "stubs.types"),
        ("lib/src/tool.py", "lib.src.tool"),
        ("__init__.py", None),
    ],
)
def test_python_module_is_the_dotted_path_without_src_and_init(path: str, module: str | None) -> None:
    assert module_path(path, no_go_module) == module


@pytest.mark.parametrize(
    ("path", "module"),
    [
        ("frontend/src/review/logic.ts", "frontend/src/review/logic"),
        ("frontend/src/components/UnitCard.tsx", "frontend/src/components/UnitCard"),
        ("web/app.js", "web/app"),
        ("web/view.jsx", "web/view"),
        ("scripts/build.mjs", "scripts/build"),
        ("config.cjs", "config"),
    ],
)
def test_script_module_is_the_file_path_without_extension(path: str, module: str) -> None:
    assert module_path(path, no_go_module) == module


@pytest.mark.parametrize(
    ("path", "module"),
    [
        ("main.go", "example.com/shop"),
        ("internal/cart/cart.go", "example.com/shop/internal/cart"),
        ("tools/lint/main.go", "example.com/lint"),
        ("tools/lint/rules/rule.go", "example.com/lint/rules"),
        ("vendor/github.com/acme/log/log.go", "github.com/acme/log"),
        ("tools/lint/vendor/golang.org/x/mod/mod.go", "golang.org/x/mod"),
    ],
)
def test_go_module_is_the_package_import_path(path: str, module: str) -> None:
    assert module_path(path, GO_MODULES.get) == module


def test_go_package_without_go_mod_falls_back_to_its_directory() -> None:
    assert module_path("pkg/cart/cart.go", no_go_module) == "pkg/cart"
    assert module_path("main.go", no_go_module) is None


def test_other_files_have_no_module() -> None:
    assert module_path("README.md", no_go_module) is None
    assert module_path("Makefile", no_go_module) is None


def test_go_module_name_reads_the_module_directive() -> None:
    assert go_module_name(b"// shop\nmodule example.com/shop // main\n\ngo 1.23\n") == "example.com/shop"
    assert go_module_name(b'module "example.com/quoted"\n') == "example.com/quoted"
    assert go_module_name(b"module\texample.com/tabbed\n") == "example.com/tabbed"
    assert go_module_name(b"module\n") is None
    assert go_module_name(b"module (\n\texample.com/block // main\n)\n") == "example.com/block"
    assert go_module_name(b"module (\n)\n") is None
    assert go_module_name(b"go 1.23\n") is None
