import threading

from storages.backends.s3 import S3Storage


class PublicSignedS3Storage(S3Storage):
    """S3/MinIO storage that uploads through the internal endpoint but signs URLs for a public one.

    SigV4 covers the host and the path, so a presigned URL is only valid for the exact host it
    was signed against. Inside compose that host is ``minio:9000``, which no browser can reach.
    ``public_endpoint_url`` is the scheme+host the browser will use; the reverse proxy in front
    of MinIO must forward the Host header and the path untouched.
    """

    def __init__(self, **settings):
        super().__init__(**settings)
        self._public_connections = threading.local()

    def get_default_settings(self):
        defaults = super().get_default_settings()
        defaults["public_endpoint_url"] = None
        return defaults

    @property
    def public_connection(self):
        connection = getattr(self._public_connections, "connection", None)
        if connection is None:
            session = self._create_session()
            connection = session.resource(
                "s3",
                region_name=self.region_name,
                use_ssl=self.use_ssl,
                endpoint_url=self.public_endpoint_url,
                config=self.client_config,
                verify=self.verify,
            )
            self._public_connections.connection = connection
        return connection

    def url(self, name, parameters=None, expire=None, http_method=None):
        if not (self.querystring_auth and self.public_endpoint_url):
            return super().url(name, parameters=parameters, expire=expire, http_method=http_method)
        name = self._normalize_name(name)
        params = dict(parameters or {})
        params["Bucket"] = self.bucket.name
        params["Key"] = name
        return self.public_connection.meta.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=self.querystring_expire if expire is None else expire,
            HttpMethod=http_method,
        )

    def __getstate__(self):
        state = super().__getstate__()
        state.pop("_public_connections", None)
        return state

    def __setstate__(self, state):
        super().__setstate__(state)
        self._public_connections = threading.local()
