from rest_framework import serializers

from .models import Submission, VerdictOverride

ANALYZER_DESCRIPTIONS = {
    "metadata": "Reads EXIF/XMP metadata. Looks for editing software signatures, missing camera fields, and timestamp inconsistencies.",
    "ela": "Error Level Analysis. Re-saves the image at a known compression and compares pixel-level differences to spot spliced or pasted regions.",
    "ai_detector": "Ensemble of 3 image classifiers (Organika SDXL detector, dima806 BeiT, umm-maybe ViT). Pre-filters non-photographic content (screenshots, diagrams, UI) since AI photo detectors are unreliable outside their training distribution. Averages AI-generated probability across models; verdict requires multi-model agreement.",
    "llm_vision": "Vision LLM (moondream). Examines lighting consistency, texture coherence, fine details (fingers, eyes, text), and overall aesthetic.",
    "video_frame": "Samples frames from the video at uniform intervals and runs ELA + AI detection on each one.",
    "audio_spectrogram": "Computes spectral features with librosa to detect synthetic-voice artifacts and unnatural frequency distributions.",
    "llm_text": "Text LLM (qwen2.5:3b). Classifies whether the input text was likely AI-generated based on stylistic and structural cues.",
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


class SubmissionDetailSerializer(serializers.ModelSerializer):
    analysis_results = serializers.SerializerMethodField()
    similar_submissions = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    expected_analyzers = serializers.SerializerMethodField()

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
            "phash",
            "dhash",
            "file_url",
            "analysis_results",
            "similar_submissions",
            "expected_analyzers",
            "created_at",
            "updated_at",
        )

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
        return find_similar_submissions(obj)

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
