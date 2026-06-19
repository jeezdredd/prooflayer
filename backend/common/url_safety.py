import ipaddress
import socket
from urllib.parse import urlparse


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
    ):
        raise UnsafeUrlError("URL not allowed")
    return url
