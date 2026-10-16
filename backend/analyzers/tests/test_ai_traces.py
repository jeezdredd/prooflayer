import json

import cv2
import numpy as np
import pytest

from analyzers.aggregator import aggregate
from analyzers.content_credentials import has_remnants, read_manifest, summarize
from analyzers.implementations.metadata_analyzer import MetadataAnalyzer
from analyzers.models import AnalysisResult
from analyzers.watermarks import KNOWN_WATERMARKS, find_known_watermark
from content.tests.factories import SubmissionFactory

from .factories import AnalysisResultFactory, AnalyzerConfigFactory

IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"


def _manifest(source_type, state="Trusted", issuer="OpenAI", generator="ChatGPT", problems=()):
    return json.dumps({
        "active_manifest": "urn:1",
        "validation_state": state,
        "validation_status": [{"code": p} for p in problems],
        "manifests": {"urn:1": {
            "claim_generator_info": [{"name": generator}, {"name": "c2pa-rs", "version": "0.70"}],
            "signature_info": {"issuer": issuer, "time": "2026-10-14T20:29:14+00:00"},
            "assertions": [{"label": "c2pa.actions.v2", "data": {"actions": [
                {"action": "c2pa.created", "digitalSourceType": IPTC + source_type, "softwareAgent": {"name": "GPT-4o"}},
            ]}}],
        }},
    })


def _embed(bgr, bits):
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV).astype(np.float64)
    u = yuv[:, :, 1]
    a, b, c, d = u[0::2, 0::2], u[0::2, 1::2], u[1::2, 0::2], u[1::2, 1::2]
    ll, h, v, dd = (a + b + c + d) / 2, (a + b - c - d) / 2, (a - b + c - d) / 2, (a - b - c + d) / 2
    br, bc = ll.shape[0] // 4, ll.shape[1] // 4
    blocks = ll[: br * 4, : bc * 4].reshape(br, 4, bc, 4).transpose(0, 2, 1, 3).reshape(-1, 16).copy()
    for n, block in enumerate(blocks):
        pos = int(np.argmax(np.abs(block[1:]))) + 1
        magnitude = (abs(block[pos]) // 36 + 0.25 + 0.5 * bits[n % len(bits)]) * 36
        block[pos] = magnitude if block[pos] >= 0 else -magnitude
    ll[: br * 4, : bc * 4] = blocks.reshape(br, bc, 4, 4).transpose(0, 2, 1, 3).reshape(br * 4, bc * 4)
    u[0::2, 0::2], u[0::2, 1::2] = (ll + h + v + dd) / 2, (ll + h - v - dd) / 2
    u[1::2, 0::2], u[1::2, 1::2] = (ll - h + v - dd) / 2, (ll - h - v + dd) / 2
    return cv2.cvtColor(np.clip(np.rint(yuv), 0, 255).astype(np.uint8), cv2.COLOR_YUV2BGR)


@pytest.fixture
def photo():
    rng = np.random.default_rng(7)
    noise = cv2.GaussianBlur(rng.normal(0, 25, (512, 512, 3)), (0, 0), 3)
    return np.clip(128 + noise, 40, 215).astype(np.uint8)


def _flux_bits():
    return next(m["bits"] for m in KNOWN_WATERMARKS if m["name"] == "FLUX.1")


class TestWatermarks:
    def test_flux_watermark_found_in_png(self, photo, tmp_path):
        path = tmp_path / "flux.png"
        cv2.imwrite(str(path), _embed(photo, _flux_bits()))
        found = find_known_watermark(str(path))
        assert found["name"] == "FLUX.1"
        assert found["vendor"] == "Black Forest Labs"
        assert found["match"] >= 0.9

    def test_unmarked_image_has_no_watermark(self, photo, tmp_path):
        path = tmp_path / "plain.png"
        cv2.imwrite(str(path), photo)
        assert find_known_watermark(str(path)) is None

    def test_small_or_missing_image_is_skipped(self, tmp_path):
        path = tmp_path / "tiny.png"
        cv2.imwrite(str(path), np.full((100, 100, 3), 128, np.uint8))
        assert find_known_watermark(str(path)) is None
        assert find_known_watermark(str(tmp_path / "missing.png")) is None


class TestContentCredentials:
    def test_trusted_openai_generation(self):
        summary = summarize(_manifest("trainedAlgorithmicMedia"))
        assert summary["ai"] == "generated"
        assert summary["trusted"] is True
        assert summary["generator"] == "ChatGPT"
        assert summary["signed_by"] == "OpenAI"

    def test_ai_edit_is_not_generation(self):
        assert summarize(_manifest("compositeWithTrainedAlgorithmicMedia"))["ai"] == "edited"

    def test_procedural_media_is_not_ai(self):
        assert summarize(_manifest("algorithmicMedia"))["ai"] is None

    def test_tampered_manifest_is_not_intact(self):
        summary = summarize(_manifest("trainedAlgorithmicMedia", state="Invalid", problems=("assertion.dataHash.mismatch",)))
        assert summary["intact"] is False
        assert summary["trusted"] is False

    def test_library_name_is_not_the_generator(self):
        summary = summarize(_manifest("trainedAlgorithmicMedia", generator="c2pa-rs"))
        assert summary["generator"] == "GPT-4o"

    def test_garbage_returns_none(self):
        assert summarize("not json") is None
        assert summarize({"manifests": {}}) is None


class TestMetadataTraces:
    def _analyze(self, path="unused.png", **metadata):
        return MetadataAnalyzer().analyze(str(path), {"format": "PNG", "width": 1024, "height": 1024, **metadata})

    def test_trusted_c2pa_generation_is_proof(self):
        out = self._analyze(c2pa_summary=summarize(_manifest("trainedAlgorithmicMedia")))
        assert out.verdict == "fake"
        assert out.evidence["provenance_proof"] is True
        assert out.evidence["ai_trace"][0] == {"kind": "c2pa", "ai": "generated", "generator": "ChatGPT", "signed_by": "OpenAI", "trusted": True, "state": "Trusted"}

    def test_untrusted_c2pa_generation_votes_fake_without_proof(self):
        out = self._analyze(c2pa_summary=summarize(_manifest("trainedAlgorithmicMedia", state="Valid", issuer="Some Self-Signed CA")))
        assert out.verdict == "fake"
        assert out.evidence["provenance_proof"] is False

    def test_c2pa_ai_edit_is_suspicious(self):
        out = self._analyze(c2pa_summary=summarize(_manifest("compositeWithTrainedAlgorithmicMedia", issuer="Adobe Inc.", generator="Adobe Photoshop")))
        assert out.verdict == "suspicious"
        assert "c2pa_ai_edited" in out.evidence["flags"]

    def test_xmp_composite_is_edit_not_generation(self):
        out = self._analyze(xmp=f'<rdf:Description Iptc4xmpExt:DigitalSourceType="{IPTC}compositeWithTrainedAlgorithmicMedia"/>')
        assert out.evidence["c2pa"]["ai_declared"] is False
        assert out.evidence["c2pa"]["ai_edited"] is True

    def test_google_iptc_credit_is_an_ai_tool_signature(self):
        out = self._analyze(xmp='<rdf:Description photoshop:Credit="Made with Google AI"/>')
        assert out.evidence["ai_tool"]["detected"] is True
        assert out.verdict == "fake"

    def test_watermark_is_proof(self, photo, tmp_path):
        path = tmp_path / "flux.png"
        cv2.imwrite(str(path), _embed(photo, _flux_bits()))
        out = self._analyze(path=path)
        assert out.evidence["provenance_proof"] is True
        assert out.evidence["watermark"]["name"] == "FLUX.1"
        assert any(t["kind"] == "watermark" for t in out.evidence["ai_trace"])


@pytest.mark.django_db
class TestProvenanceProofRule:
    def _bench(self, proof):
        sub = SubmissionFactory()
        metadata = AnalysisResultFactory(
            submission=sub, analyzer=AnalyzerConfigFactory(name="metadata", weight=1.5), confidence=0.98,
            verdict=AnalysisResult.Verdict.FAKE, evidence={"provenance_proof": proof},
        )
        detectors = [
            AnalysisResultFactory(
                submission=sub, analyzer=AnalyzerConfigFactory(name=name, weight=3.5), confidence=0.85,
                verdict=AnalysisResult.Verdict.AUTHENTIC, evidence={"ai_probability": 0.05},
            )
            for name in ("community_forensics", "custom_detector")
        ]
        return aggregate([metadata, *detectors])

    def test_proof_overrides_authentic_bench(self):
        score, verdict = self._bench(True)
        assert verdict == "fake"
        assert score >= 0.95

    def test_unproven_metadata_vote_does_not_override(self):
        _, verdict = self._bench(False)
        assert verdict != "fake"


def _damaged_bits():
    bits = list(_flux_bits())
    for i in (3, 11, 19, 27, 35):
        bits[i] = 1 - bits[i]
    return bits


def _jpeg_with_orphan_jumbf(tmp_path):
    path = tmp_path / "plain.jpg"
    cv2.imwrite(str(path), np.full((300, 300, 3), 120, np.uint8))
    data = path.read_bytes()
    payload = b"JP\x00\x01" + b"\x00\x00\x00\x10jumb" + b"\x00" * 24
    segment = b"\xff\xeb" + (len(payload) + 2).to_bytes(2, "big") + payload
    broken = tmp_path / "stripped.jpg"
    broken.write_bytes(data[:2] + segment + data[2:])
    return broken


class TestTraceHiding:
    def test_damaged_watermark_still_names_the_generator(self, photo, tmp_path):
        path = tmp_path / "damaged.png"
        cv2.imwrite(str(path), _embed(photo, _damaged_bits()))
        found = find_known_watermark(str(path))
        assert found["name"] == "FLUX.1" and found["state"] == "damaged"
        out = MetadataAnalyzer().analyze(str(path), {"format": "PNG", "width": 512, "height": 512})
        assert out.verdict == "fake"
        assert out.evidence["provenance_proof"] is False
        assert out.evidence["evasion"][0]["kind"] == "damaged_watermark"

    def test_orphan_c2pa_segment_is_a_removed_credential(self, tmp_path):
        path = _jpeg_with_orphan_jumbf(tmp_path)
        assert read_manifest(str(path)) is None
        assert has_remnants(str(path)) is True
        out = MetadataAnalyzer().analyze(str(path), {"format": "JPEG", "width": 300, "height": 300, "c2pa_remnants": True})
        assert {"kind": "credentials_removed"} in out.evidence["evasion"]
        assert out.verdict != "fake"

    def test_clean_files_have_no_remnants(self, photo, tmp_path):
        for name in ("clean.png", "clean.jpg", "clean.webp"):
            path = tmp_path / name
            cv2.imwrite(str(path), photo)
            assert has_remnants(str(path)) is False

    def test_credentials_broken_after_signing(self):
        manifest = _manifest("trainedAlgorithmicMedia", state="Invalid", problems=("assertion.dataHash.mismatch",))
        out = MetadataAnalyzer().analyze("unused.png", {"format": "PNG", "c2pa_summary": summarize(manifest)})
        assert out.evidence["evasion"] == [{"kind": "credentials_altered", "generator": "ChatGPT"}]
        assert out.verdict == "fake"
        assert out.evidence["provenance_proof"] is False
