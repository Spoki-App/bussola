import ipaddress
import secrets

TOKEN_COOKIE = "bussola_token"
TOKEN_QUERY = "token"
TOKEN_ENV = "BUSSOLA_TOKEN"
API_PATH_PREFIX = "/api/"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
INVALID_TOKEN_DETAIL = "Missing or invalid session token"
INVALID_TOKEN_CODE = "invalid_token"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_cookie(port: int | None) -> str:
    return f"{TOKEN_COOKIE}_{port}" if port else TOKEN_COOKIE


def is_local_host(host: str) -> bool:
    if host in LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_ipv6_host(host: str) -> bool:
    return ":" in host


def host_port(host: str, port: int) -> str:
    return f"[{host}]:{port}" if is_ipv6_host(host) else f"{host}:{port}"


def allowed_hosts_for(host: str, port: int) -> frozenset[str]:
    return frozenset(host_port(name, port) for name in {*LOCAL_HOSTS, host})
