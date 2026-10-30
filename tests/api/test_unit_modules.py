from tests.apiclient import ApiClient, comment_on
from tests.gitrepo import GitFixture


def start(git_repo: GitFixture, api: ApiClient) -> int:
    git_repo.commit({"go.mod": "module example.com/shop\n\ngo 1.23\n"})
    git_repo.branch("feature")
    git_repo.commit(
        {
            "src/shop/cart.py": "def total():\n    return 0\n",
            "web/src/cart.ts": "export function total() {\n  return 0\n}\n",
            "internal/cart/cart.go": "package cart\n\nfunc Total() int {\n\treturn 0\n}\n",
            "README.md": "# Shop\n",
        }
    )
    return api.start_review()


def test_units_carry_the_module_of_their_file(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)

    modules = {unit["path"]: unit["module"] for unit in api.units(review)}

    assert modules == {
        "src/shop/cart.py": "shop.cart",
        "web/src/cart.ts": "web/src/cart",
        "internal/cart/cart.go": "example.com/shop/internal/cart",
        "README.md": None,
    }


def test_threads_carry_the_module_of_their_unit(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    comment_on(api, review, "internal/cart/cart.go::Total", 1)

    threads = api.call("GET", f"/reviews/{review}/threads")

    assert [(thread["qualified_name"], thread["module"]) for thread in threads] == [("Total", "example.com/shop/internal/cart")]


def test_removed_go_files_take_their_module_from_the_base(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit(
        {
            "go.mod": "module example.com/shop\n",
            "tools/lint/go.mod": "module example.com/lint\n",
            "tools/lint/rules/rule.go": "package rules\n\nfunc Check() bool {\n\treturn true\n}\n",
        }
    )
    git_repo.branch("feature")
    git_repo.commit({"tools/lint/go.mod": None, "tools/lint/rules/rule.go": None})
    review = api.start_review()

    modules = {unit["path"]: unit["module"] for unit in api.units(review)}

    assert modules["tools/lint/rules/rule.go"] == "example.com/lint/rules"
