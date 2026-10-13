import hashlib
import hmac
import json
import time

SIGNATURE_HEADER = "X-ProofLayer-Signature"
TIMESTAMP_HEADER = "X-ProofLayer-Timestamp"
EVENT_HEADER = "X-ProofLayer-Event"
EVENT_SUBMISSION_COMPLETED = "submission.completed"


def build_payload(submission) -> dict:
    return {
        "event": EVENT_SUBMISSION_COMPLETED,
        "submission_id": str(submission.id),
        "status": submission.status,
        "verdict": submission.final_verdict,
        "score": submission.final_score,
        "tribunal_version": submission.tribunal_version,
        "tribunal_fingerprint": submission.tribunal_fingerprint,
        "original_filename": submission.original_filename,
        "completed_at": submission.updated_at.isoformat() if submission.updated_at else None,
    }


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """HMAC-SHA256 over `<timestamp>.<raw body>`; the timestamp lets receivers reject replays."""
    message = timestamp.encode("ascii") + b"." + body
    return "sha256=" + hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def encode(payload: dict, secret: str, now: float | None = None) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    timestamp = str(int(now if now is not None else time.time()))
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ProofLayer-Webhooks/1",
        EVENT_HEADER: payload["event"],
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: sign(secret, timestamp, body),
    }
    return body, headers
