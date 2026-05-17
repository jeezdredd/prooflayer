---
type: service
created: 2026-05-14
---

# MinIO (Object Store)

S3-compatible blob store. Holds uploaded submission files + thumbnails.

## Container

```yaml
minio:
  image: minio/minio:latest
  command: server /data --console-address ":9001"
  ports:
    - "9000:9000"   # S3 API
    - "9001:9001"   # web console
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin
  volumes:
    - minio_data:/data
```

## Init container

`minio_init` runs once:

```sh
mc alias set local http://minio:9000 ${USER} ${PASS}
mc mb -p local/${AWS_STORAGE_BUCKET_NAME}
mc anonymous set download local/${BUCKET}
```

Creates bucket + sets public-read for downloads (so thumbnails + result files serve directly).

## Django integration

`django-storages` with S3 backend pointed at MinIO endpoint:

```
AWS_S3_ENDPOINT_URL=http://minio:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_STORAGE_BUCKET_NAME=prooflayer-media
```

## storage_utils.local_file

Helper context manager:

```python
@contextmanager
def local_file(file_field):
    # pulls remote blob to /tmp, yields path, cleans up
```

Used by analyzers that need filesystem access (cv2.VideoCapture, PIL.Image.open with non-seekable streams, ffmpeg etc).

## See also

- [[architecture]]
- [[services/backend]]
- [[concepts/submission-pipeline]]
