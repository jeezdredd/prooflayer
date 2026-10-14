from rest_framework import serializers

from analyzers.ensemble import ensemble_info
from common.age import can_view_sensitive
from plagiarism.serializers import report_payload

from .models import Submission, VerdictOverride
from .objections import latest_objection_payload

ANALYZER_DESCRIPTIONS = {
    "metadata": "Reads EXIF/XMP metadata. Looks for editing software signatures, missing camera fields, and timestamp inconsistencies.",
    "ela": "Error Level Analysis. Re-saves the image at a known compression and compares pixel-level differences to spot spliced or pasted regions.",
    "ai_detector": "Ensemble of independent image classifiers. Pre-filters non-photographic content (screenshots, diagrams, UI) since AI photo detectors are unreliable outside their training distribution. Averages AI-generated probability across models; verdict requires multi-model agreement.",
    "llm_vision": "Vision LLM. Examines lighting consistency, texture coherence, fine details (fingers, eyes, text), and overall aesthetic.",
    "video_frame": "Samples frames from the video at uniform intervals and runs ELA + AI detection on each one.",
    "audio_spectrogram": "Computes spectral features to detect synthetic-voice artifacts and unnatural frequency distributions.",
    "llm_text": "Text LLM. Classifies whether the input text was likely AI-generated based on stylistic and structural cues.",
    "text_classifier": "ProofLayer text classifier. Multilingual encoder (en/ru/fr) fine-tuned on student essays, news and encyclopedic text against current open models, including humanizer rewrites. Calibrated per language so that only 1% of human texts in calibration score above its flag line; on its own it can flag a text but never convict it.",
    "text_genre": "Text type. Recognises an argumentative essay, narrative, retelling, literary analysis, description, report, letter or poem in en/ru/fr from cue phrases and structure, so the other checks are read in context. Never votes.",
    "text_citations": "Ghost citations check. Extracts DOIs, arXiv ids, ISBNs, links, bibliography entries and long quotes, and checks each against doi.org, arXiv, Open Library, Google Books, OpenAlex, Crossref and the web. Invented sources are a common trace of chatbot writing; a flag sends the work to review, it never convicts on its own.",
    "community_forensics": "Community Forensics ViT-S/16 trained on 2.7M images from 4803 generators (NeurIPS 2024). Outputs a continuous AI probability score. Strongest signal for photorealistic deepfakes and diffusion-generated faces.",
    "npr_detector": "NPR (Noise Pattern Residual) ViT detector. Analyzes high-frequency noise patterns left by camera sensors vs generative models. Effective against GAN and diffusion outputs that look clean to the eye but carry generator fingerprints.",
    "siglip_detector": "SigLIP-based semantic coherence detector. Measures whether image regions are semantically consistent with each other. Inpainting, face swaps, and localized edits often produce regions with mismatched semantic context.",
    "custom_detector": "ProofLayer proprietary detector. Fine-tuned on verified real/fake submissions collected by the ProofLayer community. Improves with every retrain cycle as more labeled data is approved.",
}


class SubmissionCreateSerializer(serializers.ModelSerializer):
    file = serializers.FileField()

    class Meta:
        model = Submission
        fields = ("id", "file", "status", "created_at")
        read_only_fields = ("id", "status", "created_at")


class SubmissionListSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = (
            "id",
            "original_filename",
            "mime_type",
            "file_size",
            "status",
            "final_score",
            "final_verdict",
            "is_known_fake",
            "thumbnail_url",
            "created_at",
        )

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None


class UploaderProfileSerializer(serializers.Serializer):
    username = serializers.CharField()
    avatar_url = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField()

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj.avatar:
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class PublicSubmissionSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    uploader = serializers.SerializerMethodField()
    analysis_results = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = (
            "id",
            "original_filename",
            "mime_type",
            "file_size",
            "final_score",
            "final_verdict",
            "is_known_fake",
            "is_sensitive",
            "thumbnail_url",
            "uploader",
            "analysis_results",
            "created_at",
        )

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail:
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None

    def get_uploader(self, obj):
        return {
            "username": obj.user.username,
            "date_joined": obj.user.date_joined.isoformat(),
            "avatar_url": None,
        }

    def get_analysis_results(self, obj):
        from analyzers.serializers import AnalysisResultSerializer
        return AnalysisResultSerializer(obj.analysis_results.all(), many=True).data


class SubmissionDetailSerializer(serializers.ModelSerializer):
    analysis_results = serializers.SerializerMethodField()
    similar_submissions = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    expected_analyzers = serializers.SerializerMethodField()
    ensemble = serializers.SerializerMethodField()
    originality = serializers.SerializerMethodField()
    objection = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = (
            "id",
            "original_filename",
            "mime_type",
            "file_size",
            "sha256_hash",
            "status",
            "status_message",
            "metadata",
            "final_score",
            "final_verdict",
            "is_known_fake",
            "is_public",
            "is_sensitive",
            "phash",
            "dhash",
            "file_url",
            "ensemble",
            "originality",
            "objection",
            "analysis_results",
            "similar_submissions",
            "expected_analyzers",
            "created_at",
            "updated_at",
        )

    def get_originality(self, obj):
        request = self.context.get("request")
        return report_payload(obj, getattr(request, "user", None))

    def get_objection(self, obj):
        request = self.context.get("request")
        return latest_objection_payload(obj, getattr(request, "user", None))

    def get_ensemble(self, obj):
        current = ensemble_info()
        version = obj.tribunal_version
        if not version:
            return None
        return {
            "name": current["name"],
            "version": version,
            "label": f"{current['name']} {version}",
            "fingerprint": obj.tribunal_fingerprint,
            "current_version": current["version"],
            "current_fingerprint": current["fingerprint"],
            "is_current": obj.tribunal_fingerprint == current["fingerprint"] and version == current["version"],
        }

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file:
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_analysis_results(self, obj):
        from analyzers.serializers import AnalysisResultSerializer
        return AnalysisResultSerializer(obj.analysis_results.all(), many=True).data

    def get_similar_submissions(self, obj):
        from .services import find_similar_submissions
        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        return find_similar_submissions(obj, include_sensitive=can_view_sensitive(viewer))

    def get_expected_analyzers(self, obj):
        return _expected_analyzers_for_mime(obj.mime_type or "")


_EXPECTED_CACHE: dict[str, list[dict]] = {}


def _expected_analyzers_for_mime(mime_type: str) -> list[dict]:
    cached = _EXPECTED_CACHE.get(mime_type)
    if cached is not None:
        return cached

    from analyzers.models import AnalyzerConfig
    from analyzers.registry import load_analyzer_class

    result = []
    for cfg in AnalyzerConfig.objects.filter(is_active=True).order_by("name"):
        try:
            cls = load_analyzer_class(cfg.analyzer_class)
            supported = cls().supported_mime_types()
        except Exception:
            supported = []
        if mime_type and mime_type not in supported:
            continue
        result.append({
            "name": cfg.name,
            "description": ANALYZER_DESCRIPTIONS.get(cfg.name, ""),
        })
    _EXPECTED_CACHE[mime_type] = result
    return result


class ReviewQueueSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    submitter_email = serializers.EmailField(source="user.email", read_only=True)
    override_count = serializers.IntegerField(source="verdict_overrides.count", read_only=True)

    class Meta:
        model = Submission
        fields = (
            "id",
            "original_filename",
            "mime_type",
            "file_size",
            "final_score",
            "final_verdict",
            "is_sensitive",
            "thumbnail_url",
            "submitter_email",
            "override_count",
            "created_at",
        )

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None


class VerdictOverrideSerializer(serializers.ModelSerializer):
    reviewer_email = serializers.EmailField(source="reviewer.email", read_only=True)

    class Meta:
        model = VerdictOverride
        fields = (
            "id",
            "submission",
            "reviewer_email",
            "previous_verdict",
            "new_verdict",
            "reason",
            "created_at",
        )
        read_only_fields = fields
