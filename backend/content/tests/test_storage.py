from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from content.storage import PublicSignedS3Storage

INTERNAL = "http://minio:9000"
PUBLIC = "https://media.prooflayer.cloud"


def _storage(**extra):
    opts = {
        "bucket_name": "prooflayer-media",
        "access_key": "k",
        "secret_key": "s",
        "region_name": "us-east-1",
        "endpoint_url": INTERNAL,
        "signature_version": "s3v4",
        "addressing_style": "path",
        "querystring_auth": True,
        "default_acl": None,
    }
    opts.update(extra)
    return PublicSignedS3Storage(**opts)


class TestPublicSignedUrls:
    def test_signs_against_public_endpoint(self):
        storage = _storage(public_endpoint_url=PUBLIC)
        url = storage.url("ela/abc.jpg")
        parsed = urlparse(url)
        assert f"{parsed.scheme}://{parsed.netloc}" == PUBLIC
        assert parsed.path == "/prooflayer-media/ela/abc.jpg"
        query = parse_qs(parsed.query)
        assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
        assert "X-Amz-Signature" in query

    def test_uploads_still_use_internal_endpoint(self):
        storage = _storage(public_endpoint_url=PUBLIC)
        assert storage.connection.meta.client.meta.endpoint_url == INTERNAL
        assert storage.public_connection.meta.client.meta.endpoint_url == PUBLIC

    def test_without_public_endpoint_falls_back_to_internal_signing(self):
        storage = _storage()
        assert urlparse(storage.url("x.jpg")).netloc == "minio:9000"

    def test_unsigned_mode_ignores_public_endpoint(self):
        storage = _storage(public_endpoint_url=PUBLIC, querystring_auth=False, custom_domain="cdn.example")
        assert storage.url("x.jpg") == "https://cdn.example/x.jpg"

    def test_expiry_override_reaches_signer(self):
        storage = _storage(public_endpoint_url=PUBLIC)
        client = MagicMock()
        client.generate_presigned_url.return_value = "signed"
        with patch.object(PublicSignedS3Storage, "public_connection", new=MagicMock(meta=MagicMock(client=client))):
            assert storage.url("x.jpg", expire=90) == "signed"
        assert client.generate_presigned_url.call_args.kwargs["ExpiresIn"] == 90

    @pytest.mark.parametrize("name", ["a b.jpg", "thumbnails/2026/09/15/thumb_x.jpg"])
    def test_keys_are_normalised(self, name):
        storage = _storage(public_endpoint_url=PUBLIC)
        client = MagicMock()
        client.generate_presigned_url.return_value = "signed"
        with patch.object(PublicSignedS3Storage, "public_connection", new=MagicMock(meta=MagicMock(client=client))):
            storage.url(name)
        assert client.generate_presigned_url.call_args.kwargs["Params"]["Key"] == name
