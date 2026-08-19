import socket
from unittest.mock import patch

import pytest

from common.url_safety import UnsafeUrlError, safe_get, validate_public_url


def _addrinfo(*addresses):
    return list(addresses)


class TestValidatePublicUrl:
    def test_cloud_metadata_address_blocked(self):
        with patch("common.url_safety._dns_lookup", return_value=_addrinfo("169.254.169.254")):
            with pytest.raises(UnsafeUrlError):
                validate_public_url("http://metadata.example.com/latest")

    def test_ipv6_loopback_blocked(self):
        with patch("common.url_safety._dns_lookup", return_value=_addrinfo("::1")):
            with pytest.raises(UnsafeUrlError):
                validate_public_url("http://v6.example.com/")

    def test_ipv4_mapped_ipv6_loopback_blocked(self):
        with patch("common.url_safety._dns_lookup", return_value=_addrinfo("::ffff:127.0.0.1")):
            with pytest.raises(UnsafeUrlError):
                validate_public_url("http://mapped.example.com/")

    def test_shared_address_space_blocked(self):
        with patch("common.url_safety._dns_lookup", return_value=_addrinfo("100.64.0.1")):
            with pytest.raises(UnsafeUrlError):
                validate_public_url("http://cgnat.example.com/")

    def test_any_private_answer_blocks_multi_record_host(self):
        with patch("common.url_safety._dns_lookup", return_value=_addrinfo("93.184.216.34", "10.0.0.5")):
            with pytest.raises(UnsafeUrlError):
                validate_public_url("http://mixed.example.com/")

    def test_public_address_allowed(self):
        with patch("common.url_safety._dns_lookup", return_value=_addrinfo("93.184.216.34")):
            assert validate_public_url("https://example.com/x") == "https://example.com/x"


class TestSafeGetPinning:
    def test_rebinding_between_validation_and_fetch_is_neutralised(self):
        """First two lookups answer public, later ones answer link-local."""
        answers = [_addrinfo("93.184.216.34")]

        def fake_dns(*args, **kwargs):
            return answers.pop(0) if answers else _addrinfo("169.254.169.254")

        def fake_raw_getaddrinfo(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("169.254.169.254", port))]

        seen = {}

        def fake_get(url, **kwargs):
            seen["resolved"] = socket.getaddrinfo("example.com", 443)

            class Resp:
                status_code = 200
                headers = {}

            return Resp()

        with patch("common.url_safety._dns_lookup", side_effect=fake_dns), \
             patch("common.url_safety._ORIGINAL_GETADDRINFO", side_effect=fake_raw_getaddrinfo), \
             patch("common.url_safety.requests.get", side_effect=fake_get):
            resp = safe_get("https://example.com/img.jpg")

        assert resp.status_code == 200
        assert seen["resolved"][0][4][0] == "93.184.216.34"

    def test_pin_is_cleared_after_request(self):
        with patch("common.url_safety._dns_lookup", return_value=_addrinfo("93.184.216.34")), \
             patch("common.url_safety.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.headers = {}
            safe_get("https://example.com/img.jpg")

        from common.url_safety import _local
        assert getattr(_local, "pinned", None) is None
