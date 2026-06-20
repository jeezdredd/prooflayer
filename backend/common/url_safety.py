import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests


class UnsafeUrlError(ValueError):
    pass


def validate_public_url(url: str) -> str:
    if not url or not isinstance(url, str):
        raise UnsafeUrlError("URL required")
    if not url.startswith(("http://", "https://")):
        raise UnsafeUrlError("Invalid URL")
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not host:
        raise UnsafeUrlError("Invalid URL")
    try:
        resolved_ip = ipaddress.ip_address(socket.gethostbyname(host))
    except (socket.gaierror, ValueError) as exc:
        raise UnsafeUrlError("Invalid URL") from exc
    if (
        resolved_ip.is_private
        or resolved_ip.is_loopback
        or resolved_ip.is_link_local
        or resolved_ip.is_reserved
        or resolved_ip.is_multicast
        or resolved_ip.is_unspecified
    ):
        raise UnsafeUrlError("URL not allowed")
    return url


_REDIRECT_CODES = {301, 302, 303, 307, 308}


def safe_get(url, *, timeout=10, stream=True, headers=None, max_redirects=3):
    current = url
    for _ in range(max_redirects + 1):
        validate_public_url(current)
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
