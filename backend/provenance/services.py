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
