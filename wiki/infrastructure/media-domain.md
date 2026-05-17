---
type: infrastructure
created: 2026-05-17
---

# media.prooflayer.cloud (MinIO proxy)

Public-read media files (thumbnails, submission previews) served via dedicated subdomain through Caddy + Cloudflare Tunnel.

## Why

`django-storages` generates file URLs based on `AWS_S3_ENDPOINT_URL`. Internal endpoint `http://minio:9000` only resolves inside Docker network - browsers cannot reach. Result: `<img src="...">` broken everywhere (dashboard thumbnails, ResultPage preview, VotingPanel image).

Fix: expose MinIO via public URL, point django-storages to it via `AWS_S3_CUSTOM_DOMAIN`.

## Setup

**1. MinIO bucket already public-read** via `minio_init`:
```sh
mc anonymous set download local/prooflayer-media
```

**2. MinIO port published localhost** in `deploy/compose.prod.yml`:
```yaml
ports:
  - "127.0.0.1:9000:9000"
```

**3. Caddy snippet** (`deploy/caddy.snippet`):
```caddy
http://media.prooflayer.cloud {
    encode zstd gzip
    reverse_proxy 127.0.0.1:9000 {
        header_up Host {upstream_hostport}
    }
}
```

`Host` header passes `127.0.0.1:9000` to MinIO so S3 signature verification works (MinIO validates Host).

**4. Cloudflared DNS routing** (one-time):
```bash
cloudflared tunnel route dns ubuntu-dev media.prooflayer.cloud
```

Wildcard `*.prooflayer.cloud` in `/etc/cloudflared/config.yml` already covers it - explicit route is just for the dashboard CNAME entry.

**5. Django env**:
```
AWS_S3_CUSTOM_DOMAIN=media.prooflayer.cloud
```

Now `submission.file.url` returns `https://media.prooflayer.cloud/prooflayer-media/<key>`.

## Verify

```bash
curl -I https://media.prooflayer.cloud/prooflayer-media/<sha>.jpg
# 200 OK, Content-Type: image/jpeg
```

## See also

- [[services/minio]]
- [[infrastructure/docker-compose]]
- [[concepts/submission-pipeline]]
