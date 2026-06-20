import pytest
from unittest.mock import MagicMock, patch

from common.url_safety import UnsafeUrlError, safe_get, validate_public_url


class TestValidatePublicUrl:
    def test_empty_raises(self):
        with pytest.raises(UnsafeUrlError):
            validate_public_url("")

    def test_non_http_scheme_raises(self):
        with pytest.raises(UnsafeUrlError):
            validate_public_url("ftp://example.com/x")

    @patch("common.url_safety.socket.gethostbyname", return_value="127.0.0.1")
    def test_loopback_blocked(self, mock_dns):
        with pytest.raises(UnsafeUrlError):
            validate_public_url("http://localhost/x")

    @patch("common.url_safety.socket.gethostbyname", return_value="10.0.0.5")
    def test_private_blocked(self, mock_dns):
        with pytest.raises(UnsafeUrlError):
            validate_public_url("http://internal/x")

    @patch("common.url_safety.socket.gethostbyname", return_value="169.254.169.254")
    def test_link_local_metadata_blocked(self, mock_dns):
        with pytest.raises(UnsafeUrlError):
            validate_public_url("http://metadata/x")

    @patch("common.url_safety.socket.gethostbyname", return_value="224.0.0.1")
    def test_multicast_blocked(self, mock_dns):
        with pytest.raises(UnsafeUrlError):
            validate_public_url("http://mc/x")

    @patch("common.url_safety.socket.gethostbyname", return_value="240.0.0.1")
    def test_reserved_blocked(self, mock_dns):
        with pytest.raises(UnsafeUrlError):
            validate_public_url("http://res/x")

    @patch("common.url_safety.socket.gethostbyname", return_value="::1")
    def test_ipv6_loopback_blocked(self, mock_dns):
        with pytest.raises(UnsafeUrlError):
            validate_public_url("http://v6/x")

    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    def test_public_allowed(self, mock_dns):
        assert validate_public_url("http://example.com/x") == "http://example.com/x"


class TestSafeGet:
    @patch("common.url_safety.requests.get")
    @patch("common.url_safety.socket.gethostbyname")
    def test_redirect_to_internal_blocked(self, mock_dns, mock_get):
        mock_dns.side_effect = ["93.184.216.34", "127.0.0.1"]
        redirect = MagicMock()
        redirect.status_code = 302
        redirect.headers = {"location": "http://127.0.0.1/internal"}
        mock_get.return_value = redirect
        with pytest.raises(UnsafeUrlError):
            safe_get("http://example.com/start")

    @patch("common.url_safety.requests.get")
    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    def test_direct_response_returned(self, mock_dns, mock_get):
        ok = MagicMock()
        ok.status_code = 200
        mock_get.return_value = ok
        assert safe_get("http://example.com/x") is ok

    @patch("common.url_safety.requests.get")
    @patch("common.url_safety.socket.gethostbyname", return_value="93.184.216.34")
    def test_too_many_redirects_raises(self, mock_dns, mock_get):
        loop = MagicMock()
        loop.status_code = 302
        loop.headers = {"location": "http://example.com/again"}
        mock_get.return_value = loop
        with pytest.raises(UnsafeUrlError):
            safe_get("http://example.com/start", max_redirects=2)
