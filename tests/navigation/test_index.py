from collections.abc import Callable

from bussola.navigation.index import IndexCache, build_index
from tests.gitrepo import GitFixture

FILES = {
    "shop/cart.py": "from shop.prices import price\n\n\ndef total(items):\n    return sum(price(item) for item in items)\n",
    "shop/prices.py": "def price(item):\n    return item.cost\n",
    "web/cart.ts": "export function price(item: Item): number {\n  return item.cost\n}\n",
    "web/view.tsx": "import { price } from './cart'\nexport const View = () => <b>{price(item)}</b>\n",
    "tools/legacy.js": "function price() {}\n",
    "cmd/main.go": "package main\n\nfunc price() int { return 1 }\n\nfunc main() { price() }\n",
    "vendor/lib.py": "def price():\n    pass\n",
    "README.md": "# price\n",
}


class ManualStarter:
    def __init__(self) -> None:
        self.tasks: list[Callable[[], None]] = []

    def __call__(self, task: Callable[[], None]) -> None:
        self.tasks.append(task)

    def run(self) -> None:
        tasks, self.tasks = self.tasks, []
        for task in tasks:
            task()


def test_index_lists_definitions_per_language_family(git_repo: GitFixture) -> None:
    commit = git_repo.commit(FILES)

    index = build_index(git_repo.repo, commit, ("vendor/**",), {})

    assert sorted(file.path for file, _ in index.definitions("python", "price")) == ["shop/prices.py"]
    assert sorted(file.path for file, _ in index.definitions("ecmascript", "price")) == ["tools/legacy.js", "web/cart.ts"]
    assert [file.path for file, _ in index.definitions("go", "price")] == ["cmd/main.go"]
    assert index.definitions("python", "missing") == []


def test_index_finds_the_files_that_use_a_name(git_repo: GitFixture) -> None:
    commit = git_repo.commit(FILES)

    index = build_index(git_repo.repo, commit, (), {})

    assert [file.path for file in index.files_using("python", "price")] == ["shop/cart.py"]
    assert [file.path for file in index.files_using("ecmascript", "price")] == ["web/view.tsx"]
    assert [file.path for file in index.files_using("go", "price")] == ["cmd/main.go"]


def test_index_skips_files_that_are_too_large(git_repo: GitFixture) -> None:
    commit = git_repo.commit({"big.py": "def huge():\n    pass\n" + "#" * 1_100_000 + "\n", "small.py": "def tiny():\n    pass\n"})

    index = build_index(git_repo.repo, commit, (), {})

    assert list(index.files) == ["small.py"]


def test_index_builds_in_the_background_and_is_cached_per_commit(git_repo: GitFixture) -> None:
    commit = git_repo.commit(FILES)
    starter = ManualStarter()
    cache = IndexCache(starter)

    assert cache.get(git_repo.repo, commit, ()) is None
    assert cache.get(git_repo.repo, commit, ()) is None
    assert len(starter.tasks) == 1

    starter.run()
    index = cache.get(git_repo.repo, commit, ())

    assert index is not None
    assert cache.get(git_repo.repo, commit, ()) is index
    assert starter.tasks == []


def test_a_new_commit_reuses_the_symbols_of_unchanged_files(git_repo: GitFixture) -> None:
    first = git_repo.commit(FILES)
    second = git_repo.commit({"shop/extra.py": "def extra():\n    pass\n"})
    starter = ManualStarter()
    cache = IndexCache(starter)
    cache.get(git_repo.repo, first, ())
    starter.run()
    first_index = cache.get(git_repo.repo, first, ())

    cache.get(git_repo.repo, second, ())
    starter.run()
    second_index = cache.get(git_repo.repo, second, ())

    assert first_index is not None
    assert second_index is not None
    assert second_index.files["shop/cart.py"].definitions is first_index.files["shop/cart.py"].definitions
    assert "shop/extra.py" in second_index.files
