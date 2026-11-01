from tests.apiclient import ApiClient, Json
from tests.gitrepo import GitFixture
from tests.navigation.conftest import LanguageServerPath, wait_for

PRICES = "def price(item):\n    return item.cost\n\n\ndef discount(item):\n    return 0\n"
CART = "from shop.prices import price\n\n\ndef total(items):\n    return sum(price(item) for item in items)\n"
NEW_PRICES = "def price(item):\n    return item.cost * 2\n\n\ndef discount(item):\n    return 0\n"
NEW_CART = "from shop.prices import discount, price\n\n\ndef total(items):\n    return sum(price(item) - discount(item) for item in items)\n"


def start(git_repo: GitFixture, api: ApiClient) -> int:
    git_repo.commit({"shop/prices.py": PRICES, "shop/cart.py": CART})
    git_repo.branch("feature")
    git_repo.commit({"shop/prices.py": NEW_PRICES, "shop/cart.py": NEW_CART})
    return api.start_review()


def click(api: ApiClient, review: int, path: str, line: int, text: str) -> Json:
    source = NEW_CART if path == "shop/cart.py" else NEW_PRICES
    column = source.split("\n")[line - 1].index(text) + 1
    query = f"path={path}&line={line}&column={column}"
    return wait_for(lambda: api.call("GET", f"/reviews/{review}/navigation?{query}"), lambda result: result["ready"])


def targets(result: Json) -> list[tuple[str, str, int, str]]:
    return [(target["role"], target["path"], target["line"], target["preview"]) for target in result["targets"]]


def test_a_reference_lists_its_definition_and_marks_it_in_review(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)

    result = click(nav_api, review, "shop/cart.py", 5, "price(item)")

    assert (result["symbol"], result["origin"], result["resolver"]) == ("price", "reference", "tree-sitter")
    assert targets(result) == [("definition", "shop/prices.py", 1, "def price(item):")]
    assert result["targets"][0]["unit_id"] == nav_api.unit(review, "shop/prices.py::price")["id"]
    assert result["targets"][0]["column"] == 4


def test_a_definition_outside_the_review_has_no_unit(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)

    result = click(nav_api, review, "shop/cart.py", 5, "discount(item)")

    assert targets(result) == [("definition", "shop/prices.py", 5, "def discount(item):")]
    assert result["targets"][0]["unit_id"] is None


def test_a_definition_lists_its_usages(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)

    result = click(nav_api, review, "shop/prices.py", 1, "price")

    assert (result["symbol"], result["origin"]) == ("price", "definition")
    assert targets(result) == [
        ("usage", "shop/cart.py", 1, "from shop.prices import discount, price"),
        ("usage", "shop/cart.py", 5, "return sum(price(item) - discount(item) for item in items)"),
    ]
    assert [target["unit_id"] for target in result["targets"]] == [
        nav_api.unit(review, "shop/cart.py")["id"],
        nav_api.unit(review, "shop/cart.py::total")["id"],
    ]


def test_the_base_side_resolves_at_the_merge_base(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)
    column = CART.split("\n")[4].index("price(item)") + 1

    result = wait_for(
        lambda: nav_api.call("GET", f"/reviews/{review}/navigation?path=shop/cart.py&line=5&column={column}&side=base"),
        lambda result: result["ready"],
    )

    assert targets(result) == [("definition", "shop/prices.py", 1, "def price(item):")]
    assert result["targets"][0]["side"] == "base"
    assert result["targets"][0]["unit_id"] == nav_api.unit(review, "shop/prices.py::price")["id"]


def test_clicking_outside_a_name_finds_nothing(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)

    result = nav_api.call("GET", f"/reviews/{review}/navigation?path=shop/cart.py&line=2&column=0")

    assert result == {"ready": True, "symbol": None, "origin": None, "resolver": "tree-sitter", "targets": [], "server_hint": None}


def test_the_index_can_be_prepared_ahead_of_the_first_click(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)

    result = wait_for(lambda: nav_api.call("POST", f"/reviews/{review}/navigation/index"), lambda result: result["ready"])

    assert result == {"ready": True}


def test_a_missing_language_server_comes_with_an_install_hint(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)

    result = click(nav_api, review, "shop/cart.py", 5, "price(item)")

    assert result["server_hint"] == {"family": "python", "language": "Python", "install": "uv tool install basedpyright"}


def test_an_installed_language_server_gives_the_results(nav_api: ApiClient, git_repo: GitFixture, servers: LanguageServerPath) -> None:
    servers.install("basedpyright-langserver", definition=[{"path": "shop/prices.py", "line": 4, "character": 4}])
    review = start(git_repo, nav_api)
    column = NEW_CART.split("\n")[4].index("price(item)") + 1

    result = wait_for(
        lambda: nav_api.call("GET", f"/reviews/{review}/navigation?path=shop/cart.py&line=5&column={column}"),
        lambda result: result["resolver"] == "language-server",
    )

    assert targets(result) == [("definition", "shop/prices.py", 5, "def discount(item):")]
    assert result["server_hint"] is None
    request = next(message for message in servers.messages() if message.get("method") == "textDocument/definition")
    assert request["params"]["position"] == {"line": 4, "character": column - 1}


def test_a_failing_language_server_falls_back_to_the_index(nav_api: ApiClient, git_repo: GitFixture, servers: LanguageServerPath) -> None:
    servers.install("basedpyright-langserver", mode="crash")
    review = start(git_repo, nav_api)
    click(nav_api, review, "shop/cart.py", 5, "price(item)")
    wait_for(servers.methods, lambda methods: "initialize" in methods)

    result = click(nav_api, review, "shop/cart.py", 5, "price(item)")

    assert (result["resolver"], targets(result)) == ("tree-sitter", [("definition", "shop/prices.py", 1, "def price(item):")])
    assert result["server_hint"] is None


def test_the_source_of_a_file_is_served_at_the_reviewed_revision(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)
    git_repo.write({"shop/prices.py": "not committed\n"})
    revision = nav_api.call("GET", f"/reviews/{review}")["latest_revision"]

    head = nav_api.call("GET", f"/reviews/{review}/source?path=shop/prices.py")
    base = nav_api.call("GET", f"/reviews/{review}/source?path=shop/prices.py&side=base")

    assert (head["text"], head["commit"], head["url"]) == (NEW_PRICES, revision["head_sha"], None)
    assert (base["text"], base["commit"]) == (PRICES, revision["merge_base_sha"])


def test_the_source_links_to_github_when_the_branch_has_a_github_remote(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)
    git_repo.git("remote", "add", "origin", "git@github.com:acme/widgets.git")
    head_sha = nav_api.call("GET", f"/reviews/{review}")["latest_revision"]["head_sha"]

    source = nav_api.call("GET", f"/reviews/{review}/source?path=shop/prices.py")

    assert source["url"] == f"https://github.com/acme/widgets/blob/{head_sha}/shop/prices.py"


def test_a_missing_file_is_not_found(nav_api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, nav_api)

    nav_api.call("GET", f"/reviews/{review}/source?path=shop/missing.py", 404)


def test_a_file_too_large_to_show_is_refused(nav_api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"data.py": "#" * 2_100_000 + "\n"})
    review = start(git_repo, nav_api)

    nav_api.call("GET", f"/reviews/{review}/source?path=data.py", 400)
