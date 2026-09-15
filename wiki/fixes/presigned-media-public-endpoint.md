---
type: fix
created: 2026-09-15
source: backend/content/storage.py, backend/config/settings/prod.py, deploy/caddy.snippet
---

# Presigned media URLs pointed at minio:9000

## Symptom
After the private-media change ([[fixes/audit-2026-08]], second pass) every ELA heatmap on the
result page rendered as a broken image; thumbnails and `file_url` were affected the same way.

## Cause
`MEDIA_PRIVATE=true` switched storage to `querystring_auth` and dropped `custom_domain`, so
django-storages signed URLs against `AWS_S3_ENDPOINT_URL` - `http://minio:9000`, the compose
service name. Verified on the server:

```
http://minio:9000/prooflayer-media/ela/35e9c568-...jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&...
```

Signing against the public host is not enough on its own: SigV4 covers the **Host header and
the path**, and the Caddy block for `media.prooflayer.cloud` did `rewrite * /prooflayer-media{path}`
plus `header_up Host {upstream_hostport}`, which breaks both.

## Fix
- `content.storage.PublicSignedS3Storage`: uploads and API calls keep the internal endpoint;
  `url()` signs with a second boto3 resource pointed at `public_endpoint_url`, same
  `client_config` (s3v4, path style). `AWS_S3_PUBLIC_ENDPOINT_URL` defaults to
  `https://$AWS_S3_CUSTOM_DOMAIN`.
- Caddy `media.prooflayer.cloud`: only prefix the bucket when the path does not already start
  with `/prooflayer-media/`, and forward the original Host. Snippet in `deploy/caddy.snippet`;
  the live `/etc/caddy/Caddyfile` is edited by hand on the server (`sudo`, then `caddy reload`).
- Frontend hides `heatmap_path` from the evidence JSON like it hides `heatmap_url`.

Signed URLs expire after `AWS_QUERYSTRING_EXPIRE` (3600 s); the serializer re-signs from
`heatmap_path` on every read, so nothing is stored that can rot.
