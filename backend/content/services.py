import hashlib
import io

from PIL import Image, ExifTags


def compute_sha256(file):
    sha256 = hashlib.sha256()
    file.seek(0)
    for chunk in iter(lambda: file.read(65536), b""):
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()


def extract_metadata(file_path):
    try:
        img = Image.open(file_path)
    except Exception:
        return {}

    metadata = {
        "format": img.format,
        "mode": img.mode,
        "width": img.width,
        "height": img.height,
    }

    exif_data = img.getexif()
    if exif_data:
        exif = {}
        for tag_id, value in exif_data.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            try:
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                str(value)
                exif[tag_name] = value
            except Exception:
                exif[tag_name] = str(value)
        metadata["exif"] = exif

    return metadata


def generate_thumbnail(file_path, size=(300, 300)):
    try:
        img = Image.open(file_path)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        return buffer
    except Exception:
        return None


def check_known_fake(sha256_hash):
    from .models import KnownFakeHash
    return KnownFakeHash.objects.filter(sha256_hash=sha256_hash).exists()
