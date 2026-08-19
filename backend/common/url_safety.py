import contextlib
import ipaddress
import socket
import threading
from urllib.parse import urljoin, urlparse

import requests


class UnsafeUrlError(ValueError):
    pass


_local = threading.local()
_ORIGINAL_GETADDRINFO = socket.getaddrinfo


def _is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _dns_lookup(host: str) -> list[str]:
    """Every address the host resolves to, v4 and v6."""
    infos = _ORIGINAL_GETADDRINFO(host, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def _resolve_all(host: str) -> list[str]:
    try:
        addresses = _dns_lookup(host)
    except socket.gaierror as exc:
        raise UnsafeUrlError("Invalid URL") from exc
    if isinstance(addresses, str):
        addresses = [addresses]
    if not addresses:
        raise UnsafeUrlError("Invalid URL")
    return list(addresses)


def resolve_and_validate(url: str) -> tuple[str, list[str]]:
    """Return (host, validated addresses). Raises UnsafeUrlError if any is not public."""
    if not url or not isinstance(url, str):
        raise UnsafeUrlError("URL required")
    if not url.startswith(("http://", "https://")):
        raise UnsafeUrlError("Invalid URL")
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not host:
        raise UnsafeUrlError("Invalid URL")

    addresses = _resolve_all(host)
    for address in addresses:
        try:
            resolved_ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeUrlError("Invalid URL") from exc
        if _is_blocked(resolved_ip):
            raise UnsafeUrlError("URL not allowed")
    return host, addresses


def validate_public_url(url: str) -> str:
    resolve_and_validate(url)
    return url


def _pinned_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    pinned = getattr(_local, "pinned", None)
    if pinned and host in pinned:
        results = []
        for address in pinned[host]:
            ip = ipaddress.ip_address(address)
            af = socket.AF_INET6 if ip.version == 6 else socket.AF_INET
            if family not in (0, af):
                continue
            sockaddr = (address, port, 0, 0) if ip.version == 6 else (address, port)
            results.append((af, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr))
        if results:
            return results
        raise socket.gaierror(socket.EAI_NONAME, "pinned address family unavailable")
    return _ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)


@contextlib.contextmanager
def _pin_host(host: str, addresses: list[str]):
    """Force this thread's DNS for `host` to the already-validated addresses.

    Without pinning, requests re-resolves the hostname after validation, so an
    attacker-controlled DNS record can return a public IP to the validator and a
    private one to the actual connection (DNS rebinding).
    """
    previous = getattr(_local, "pinned", None)
    _local.pinned = {**(previous or {}), host: addresses}
    if socket.getaddrinfo is not _pinned_getaddrinfo:
        socket.getaddrinfo = _pinned_getaddrinfo
    try:
        yield
    finally:
        if previous is None:
            _local.pinned = None
        else:
            _local.pinned = previous


_REDIRECT_CODES = {301, 302, 303, 307, 308}


def safe_get(url, *, timeout=10, stream=True, headers=None, max_redirects=3):
    current = url
    for _ in range(max_redirects + 1):
        host, addresses = resolve_and_validate(current)
        with _pin_host(host, addresses):
            resp = requests.get(
                current,
                timeout=timeout,
                stream=stream,
                headers=headers,
                allow_redirects=False,
            )
        if resp.status_code in _REDIRECT_CODES:
            loc = resp.headers.get("location")
            if not loc:
                return resp
            resp.close()
            current = urljoin(current, loc)
            continue
        return resp
    raise UnsafeUrlError("too many redirects")
