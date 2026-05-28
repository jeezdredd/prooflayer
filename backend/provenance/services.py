import base64
import logging

import requests as http_requests
from django.conf import settings

from content.storage_utils import local_file

logger = logging.getLogger(__name__)


def run_phash_lookup(submission):
    from content.services import find_similar_submissions
    from .models import ProvenanceResult

    similar = find_similar_submissions(submission, threshold=15)
    results = []
    for match in similar:
        distance = match["distance"]
        similarity = round(1.0 - distance / 64.0, 4)
        r = ProvenanceResult.objects.create(
            submission=submission,
            source_type=ProvenanceResult.SourceType.PHASH_MATCH,
            title=match["filename"],
            similarity_score=similarity,
            raw_data={"submission_id": match["id"], "distance": distance},
        )
        results.append(r)
    return results


def run_tineye_search(submission):
    from .models import ProvenanceResult

    api_key = getattr(settings, "TINEYE_API_KEY", None)
    if not api_key:
        return []

    try:
        with local_file(submission.file) as path, open(path, "rb") as f:
            response = http_requests.post(
                "https://api.tineye.com/rest/search/",
                headers={"x-api-key": api_key},
                files={"image": f},
                timeout=30,
            )
        response.raise_for_status()
        data = response.json()
        results = []
        for match in data.get("results", {}).get("matches", [])[:10]:
            domains = match.get("domains", [{}])
            domain = domains[0] if domains else {}
            r = ProvenanceResult.objects.create(
                submission=submission,
                source_type=ProvenanceResult.SourceType.TINEYE,
                source_url=domain.get("url", ""),
                title=domain.get("name", ""),
                similarity_score=match.get("score"),
                raw_data=match,
            )
            results.append(r)
        return results
    except Exception as exc:
        logger.warning("TinEye search failed: %s", exc)
        return []


def run_google_vision_search(submission):
    from .models import ProvenanceResult

    api_key = getattr(settings, "GOOGLE_VISION_KEY", None)
    if not api_key:
        return []

    try:
        with local_file(submission.file) as path, open(path, "rb") as f:
            image_content = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "requests": [
                {
                    "image": {"content": image_content},
                    "features": [{"type": "WEB_DETECTION", "maxResults": 10}],
                }
            ]
        }
        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
        response = http_requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        web = data["responses"][0].get("webDetection", {})
        results = []
        for page in web.get("pagesWithMatchingImages", [])[:10]:
            r = ProvenanceResult.objects.create(
                submission=submission,
                source_type=ProvenanceResult.SourceType.GOOGLE_VISION,
                source_url=page.get("url", ""),
                title=page.get("pageTitle", ""),
                raw_data=page,
            )
            results.append(r)
        return results
    except Exception as exc:
        logger.warning("Google Vision search failed: %s", exc)
        return []


PHASH_KNOWN_FAKE_THRESHOLD = 6
CLIP_NEAREST_LIMIT = 5
CLIP_COSINE_DISTANCE_MAX = 0.15


def check_perceptual_known_fake(submission) -> bool:
    """Check if submission's perceptual hash matches a known fake within Hamming threshold."""
    from content.models import KnownFakeHash

    if submission.phash is None:
        return False
    qs = KnownFakeHash.objects.raw(
        """
        SELECT id, sha256_hash, source,
               bit_count((phash # %s)::bit(64)) AS distance
        FROM known_fake_hashes
        WHERE phash IS NOT NULL
          AND bit_count((phash # %s)::bit(64)) <= %s
        ORDER BY distance ASC
        LIMIT 1
        """,
        [submission.phash, submission.phash, PHASH_KNOWN_FAKE_THRESHOLD],
    )
    matches = list(qs)
    if matches:
        logger.info(
            "perceptual known-fake match: submission=%s known=%s distance=%s source=%s",
            submission.id, matches[0].sha256_hash[:16], matches[0].distance, matches[0].source,
        )
        return True
    return False


def find_clip_neighbors(submission, limit: int = CLIP_NEAREST_LIMIT,
                        max_distance: float = CLIP_COSINE_DISTANCE_MAX):
    """Cosine-nearest neighbours using pgvector HNSW. Returns list of dicts."""
    from pgvector.django import CosineDistance

    from content.models import Submission

    if submission.clip_embedding is None:
        return []
    qs = (
        Submission.objects
        .exclude(id=submission.id)
        .exclude(clip_embedding=None)
        .annotate(distance=CosineDistance("clip_embedding", submission.clip_embedding))
        .filter(distance__lte=max_distance)
        .order_by("distance")[:limit]
    )
    return [
        {
            "id": str(s.id),
            "filename": s.original_filename,
            "distance": float(s.distance),
            "similarity": round(1.0 - float(s.distance), 4),
            "verdict": s.final_verdict,
        }
        for s in qs
    ]


def scan_provenance(submission) -> list:
    """Run cheap provenance lookups: phash hamming + CLIP cosine + C2PA. No external APIs."""
    results = []
    try:
        results.extend(run_phash_lookup(submission))
    except Exception:
        logger.exception("phash provenance failed for %s", submission.id)
    try:
        results.extend(run_clip_neighbor_lookup(submission))
    except Exception:
        logger.exception("clip provenance failed for %s", submission.id)
    try:
        r = extract_c2pa(submission)
        if r:
            results.append(r)
    except Exception:
        logger.exception("c2pa provenance failed for %s", submission.id)
    return results


def run_clip_neighbor_lookup(submission):
    from .models import ProvenanceResult

    neighbours = find_clip_neighbors(submission)
    results = []
    for n in neighbours:
        r = ProvenanceResult.objects.create(
            submission=submission,
            source_type=ProvenanceResult.SourceType.CLIP_NEIGHBOUR,
            title=n["filename"],
            similarity_score=n["similarity"],
            raw_data={"submission_id": n["id"], "cosine_distance": n["distance"], "verdict": n["verdict"], "method": "clip_cosine"},
        )
        results.append(r)
    return results


def extract_c2pa(submission):
    from .models import ProvenanceResult

    try:
        import c2pa
    except ImportError:
        return None

    try:
        with local_file(submission.file) as path:
            manifest_json = c2pa.read_file(path, None)
        if not manifest_json:
            return None
        r = ProvenanceResult.objects.create(
            submission=submission,
            source_type=ProvenanceResult.SourceType.C2PA,
            title="C2PA Content Credentials",
            raw_data={"manifest": manifest_json},
        )
        return r
    except Exception as exc:
        logger.warning("C2PA extraction failed: %s", exc)
        return None
