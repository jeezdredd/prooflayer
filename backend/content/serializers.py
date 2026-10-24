from rest_framework import serializers

from analyzers.ensemble import ensemble_info
from plagiarism.serializers import report_payload

from .models import Submission, VerdictOverride
from .objections import latest_objection_payload
from .viewer import viewer_info

ANALYZER_DESCRIPTIONS = {
    "metadata": "Reads the labels stored inside the file: which program made it, camera details, dates, and the marks AI generators leave on purpose.",
    "ela": "Looks for pieces pasted in from another picture: they compress differently from the rest. Works only on JPEG photos.",
    "ai_detector": "A set of detectors trained to tell AI pictures from photos. Screenshots and diagrams are skipped, because such detectors often get them wrong.",
    "llm_vision": "A model that looks at the picture the way a person would: hands, eyes, lettering, light and shadows.",
    "video_frame": "Takes frames from the video at even steps and checks each one like a picture.",
    "audio_spectrogram": "Listens for traces of a synthetic voice in the sound.",
    "llm_text": "Text LLM. Classifies whether the input text was likely AI-generated based on stylistic and structural cues.",
    "text_classifier": "ProofLayer text classifier. Multilingual encoder (en/ru/fr) fine-tuned on student essays, news and encyclopedic text against current open models, including humanizer rewrites. Calibrated per language so that only 1% of human texts in calibration score above its flag line; on its own it can flag a text but never convict it.",
    "text_shadow": "Assignment shadow. Compares a class submission with AI answers the teacher generated for the class's assignments, sentence by sentence and in order. A close, same-order match sends the work to review; it never convicts on its own.",
    "text_genre": "Text type. Recognises an argumentative essay, narrative, retelling, literary analysis, description, report, letter or poem in en/ru/fr from cue phrases and structure, so the other checks are read in context. Never votes.",
    "text_citations": "Ghost citations check. Extracts DOIs, arXiv ids, ISBNs, links, bibliography entries and long quotes, and checks each against doi.org, arXiv, Open Library, Google Books, OpenAlex, Crossref and the web. Invented sources are a common trace of chatbot writing; a flag sends the work to review, it never convicts on its own.",
    "community_forensics": "A detector trained on millions of pictures from thousands of AI generators. Strongest on realistic photos and faces.",
    "npr_detector": "Looks at the fine noise in the picture: a camera leaves different noise than an AI generator.",
    "siglip_detector": "Checks whether all parts of the picture fit together. Swapped faces and pasted pieces often do not.",
    "custom_detector": "Our own detector, retrained regularly on checked pictures and new AI generators.",
    "clip_probe": "Compares the picture with many known AI pictures and photos and says which it resembles more.",
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
    file_url = serializers.SerializerMethodField()
    expected_analyzers = serializers.SerializerMethodField()
    ensemble = serializers.SerializerMethodField()
    originality = serializers.SerializerMethodField()
    objection = serializers.SerializerMethodField()
    in_class = serializers.SerializerMethodField()
    viewer_role = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    classroom_name = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    can_object = serializers.SerializerMethodField()
    can_publish = serializers.SerializerMethodField()

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
            "in_class",
            "viewer_role",
            "student_name",
            "classroom_name",
            "classroom",
            "can_object",
            "can_publish",
            "analysis_results",
            "expected_analyzers",
            "created_at",
            "updated_at",
        )

    def _viewer(self, obj) -> dict:
        cache = self.context.setdefault("viewer_info", {})
        if obj.pk not in cache:
            request = self.context.get("request")
            cache[obj.pk] = viewer_info(obj, getattr(request, "user", None))
        return cache[obj.pk]

    def get_viewer_role(self, obj):
        return self._viewer(obj)["role"]

    def get_student_name(self, obj):
        return self._viewer(obj)["student_name"]

    def get_classroom_name(self, obj):
        classroom = self._viewer(obj)["classroom"]
        return classroom["name"] if classroom else None

    def get_classroom(self, obj):
        return self._viewer(obj)["classroom"]

    def get_can_object(self, obj):
        return self._viewer(obj)["can_object"]

    def get_can_publish(self, obj):
        return self._viewer(obj)["can_publish"]

    def get_originality(self, obj):
        request = self.context.get("request")
        return report_payload(obj, getattr(request, "user", None))

    def get_in_class(self, obj):
        return obj.classroom_id is not None

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
