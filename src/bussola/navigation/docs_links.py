import sys
from collections.abc import Callable
from urllib.parse import quote, urlsplit

PYTHON_DOCS = "https://docs.python.org/3/library/{page}.html"
NODE_DOCS = "https://nodejs.org/api/{module}.html"
GO_DOCS = "https://pkg.go.dev/{path}"
NODE_SCHEME = "node:"
NODE_BUILTINS = frozenset(
    {
        *("assert", "async_hooks", "buffer", "child_process", "cluster", "console", "crypto", "dgram", "dns", "events", "fs", "http", "http2"),
        *("https", "inspector", "module", "net", "os", "path", "perf_hooks", "process", "querystring", "readline", "repl", "stream"),
        *("string_decoder", "timers", "tls", "tty", "url", "util", "v8", "vm", "worker_threads", "zlib"),
    }
)
PYTHON_SUBMODULE_PAGES = frozenset(
    {
        *("os.path", "collections.abc", "concurrent.futures", "unittest.mock", "logging.config", "logging.handlers", "importlib.metadata"),
        *("importlib.resources", "urllib.request", "urllib.parse", "urllib.error", "urllib.robotparser", "http.client", "http.server"),
        *("http.cookies", "http.cookiejar", "xml.etree.elementtree", "xml.dom.minidom", "email.message", "email.utils", "html.parser"),
        *("xmlrpc.client", "xmlrpc.server", "multiprocessing.shared_memory", "tkinter.ttk"),
    }
)
DJANGO_DOCS = "https://docs.djangoproject.com/en/{version}/"
DJANGO_PAGES = {
    "django.shortcuts": "topics/http/shortcuts/",
    "django.http": "ref/request-response/",
    "django.urls.path": "ref/urls/",
    "django.urls.re_path": "ref/urls/",
    "django.urls.include": "ref/urls/",
    "django.urls.reverse": "ref/urlresolvers/",
    "django.urls.reverse_lazy": "ref/urlresolvers/",
    "django.urls.resolve": "ref/urlresolvers/",
    "django.db.models.Model": "ref/models/instances/",
    "django.db.models.Q": "ref/models/querysets/",
    "django.db.models.F": "ref/models/expressions/",
    "django.db.models.ForeignKey": "ref/models/fields/",
    "django.db.models.ManyToManyField": "ref/models/fields/",
    "django.db.models.OneToOneField": "ref/models/fields/",
}
DJANGO_FIELDS_PAGE = "ref/models/fields/"
DJANGO_MODELS = "django.db.models."
FIELD_SUFFIX = "Field"
FASTAPI_PAGES = {
    **dict.fromkeys(("FastAPI",), "fastapi"),
    **dict.fromkeys(("APIRouter",), "apirouter"),
    **dict.fromkeys(("Query", "Path", "Body", "Cookie", "Header", "Form", "File"), "parameters"),
    **dict.fromkeys(("Depends", "Security"), "dependencies"),
    **dict.fromkeys(("HTTPException", "WebSocketException"), "exceptions"),
    **dict.fromkeys(("Request",), "request"),
    **dict.fromkeys(("Response",), "response"),
    **dict.fromkeys(("UploadFile",), "uploadfile"),
    **dict.fromkeys(("BackgroundTasks",), "background"),
    **dict.fromkeys(("WebSocket",), "websockets"),
}
FASTAPI_DOCS = "https://fastapi.tiangolo.com/reference/{page}/#{qualified}"
FLASK_DOCS = "https://flask.palletsprojects.com/en/stable/api/#{qualified}"
REQUESTS_DOCS = "https://requests.readthedocs.io/en/latest/api/#{qualified}"
NUMPY_DOCS = "https://numpy.org/doc/stable/reference/generated/{qualified}.html"
NUMPY_WITHOUT_PAGE = frozenset({"pi", "e", "inf", "nan", "newaxis", "euler_gamma", "typing"})
PANDAS_DOCS = "https://pandas.pydata.org/docs/reference/api/{qualified}.html"
READTHEDOCS_HOST = ".readthedocs.io"
READTHEDOCS_SEARCH = "search.html?q={query}"
READTHEDOCS_DEFAULT_VERSION = "en/latest/"
REACT_DOCS = "https://react.dev/reference/{package}/{name}"
REACT_PACKAGES = frozenset({"react", "react-dom", "react-dom/client", "react-dom/server", "react-dom/static"})
REACT_COMPONENTS = frozenset({"Children", "Component", "PureComponent", "Fragment", "Profiler", "StrictMode", "Suspense"})
REACT_WITHOUT_PAGE = frozenset({"version"})
LODASH_DOCS = "https://lodash.com/docs/#{name}"
LODASH_PACKAGES = ("lodash", "lodash-es")
EXPRESS_DOCS = "https://expressjs.com/en/api.html#express.{name}"
EXPRESS_FUNCTIONS = frozenset({"json", "raw", "Router", "static", "text", "urlencoded"})

type PythonDocs = Callable[[list[str], str | None], str | None]


def symbol_docs_url(family: str, module: str, name: str, version: str | None, docs_base: str | None) -> str | None:
    if family == "python":
        return _python_url(module, name, version, docs_base)
    if family == "ecmascript":
        return _script_url(module, name)
    return GO_DOCS.format(path=module) + (f"#{name}" if name else "")


def node_builtin(module: str) -> str | None:
    first = module.removeprefix(NODE_SCHEME).split("/")[0]
    return first if module.startswith(NODE_SCHEME) or first in NODE_BUILTINS else None


def _python_url(module: str, name: str, version: str | None, docs_base: str | None) -> str | None:
    parts = [*module.split("."), *(name.split(".") if name else [])]
    qualified = ".".join(parts)
    if parts[0] in sys.stdlib_module_names:
        return PYTHON_DOCS.format(page=_python_page(parts)) + (f"#{qualified}" if name else "")
    framework = PYTHON_FRAMEWORKS.get(parts[0])
    url = framework(parts, version) if framework is not None and name else None
    if url is None and docs_base is not None and name and urlsplit(docs_base).netloc.endswith(READTHEDOCS_HOST):
        return _readthedocs_search(docs_base, qualified)
    return url


def _python_page(parts: list[str]) -> str:
    prefixes = (".".join(parts[:end]).lower() for end in range(len(parts), 1, -1))
    return next((prefix for prefix in prefixes if prefix in PYTHON_SUBMODULE_PAGES), parts[0].lower())


def _django(parts: list[str], version: str | None) -> str | None:
    qualified = ".".join(parts)
    base = DJANGO_DOCS.format(version=".".join(version.split(".")[:2]) if version else "stable")
    page = next((page for prefix, page in DJANGO_PAGES.items() if qualified == prefix or qualified.startswith(f"{prefix}.")), None)
    symbol = qualified.removeprefix(DJANGO_MODELS).split(".")[0] if qualified.startswith(DJANGO_MODELS) else ""
    if page is None and symbol.endswith(FIELD_SUFFIX):
        page = DJANGO_FIELDS_PAGE
    return f"{base}{page}#{qualified}" if page is not None else f"{base}search/?q={quote(qualified)}"


def _fastapi(parts: list[str], _version: str | None) -> str | None:
    page = FASTAPI_PAGES.get(parts[1]) if len(parts) > 1 else None
    return FASTAPI_DOCS.format(page=page, qualified=".".join(parts)) if page is not None else None


def _flask(parts: list[str], _version: str | None) -> str | None:
    return FLASK_DOCS.format(qualified=".".join(parts))


def _requests(parts: list[str], _version: str | None) -> str | None:
    return REQUESTS_DOCS.format(qualified=".".join(parts))


def _numpy(parts: list[str], _version: str | None) -> str | None:
    return NUMPY_DOCS.format(qualified=".".join(parts)) if parts[1] not in NUMPY_WITHOUT_PAGE else None


def _pandas(parts: list[str], _version: str | None) -> str | None:
    return PANDAS_DOCS.format(qualified=".".join(parts))


PYTHON_FRAMEWORKS: dict[str, PythonDocs] = {
    "django": _django,
    "fastapi": _fastapi,
    "flask": _flask,
    "requests": _requests,
    "numpy": _numpy,
    "pandas": _pandas,
}


def _readthedocs_search(docs_base: str, qualified: str) -> str:
    base = docs_base if docs_base.endswith("/") else f"{docs_base}/"
    version = "" if urlsplit(base).path.strip("/") else READTHEDOCS_DEFAULT_VERSION
    return f"{base}{version}{READTHEDOCS_SEARCH.format(query=quote(qualified))}"


def _script_url(module: str, name: str) -> str | None:
    first = name.split(".", maxsplit=1)[0] if name else ""
    builtin = node_builtin(module)
    if builtin is not None:
        return NODE_DOCS.format(module=builtin) + (f"#:~:text={quote(first if first[:1].isupper() else f'{builtin}.{first}')}" if first else "")
    if module in REACT_PACKAGES and first and first not in REACT_WITHOUT_PAGE and (first[:1].islower() or first in REACT_COMPONENTS):
        return REACT_DOCS.format(package=module, name=first)
    lodash = _lodash_function(module, first)
    if lodash:
        return LODASH_DOCS.format(name=lodash)
    if module == "express" and first in EXPRESS_FUNCTIONS:
        return EXPRESS_DOCS.format(name=first)
    return None


def _lodash_function(module: str, first: str) -> str | None:
    if module in LODASH_PACKAGES:
        return first or None
    for package in LODASH_PACKAGES:
        if module.startswith(f"{package}/") or module.startswith(f"{package}."):
            return module[len(package) + 1 :] or None
    return None
