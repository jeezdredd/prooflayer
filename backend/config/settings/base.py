import os
from datetime import timedelta
from pathlib import Path

from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-in-production")

INSTALLED_APPS = [
    "daphne",
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "api",
    "users",
    "content",
    "analyzers",
    "crowdsource",
    "reports",
    "provenance",
    "factcheck",
    "drf_spectacular",
    "pgvector.django",
    "channels",
    "billing",
    "classroom",
    "plagiarism",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [os.environ.get("REDIS_URL", "redis://localhost:6379/0")]},
    }
}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "users.authentication.ApiKeyAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "content.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "common.throttling.StaffBypassAnonRateThrottle",
        "common.throttling.StaffBypassUserRateThrottle",
        "common.throttling.ApiKeyRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/hour",
        "public": "600/hour",
        "user": "500/hour",
        "upload": "30/hour",
        "register": "5/hour",
        "login": "20/hour",
        "resend_verification": "5/hour",
        "password_reset": "5/hour",
        "widget": "120/hour",
        "api": "120/min",
        "batch": "10/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ProofLayer API",
    "DESCRIPTION": "Multi-modal AI content verification platform. Detects deepfakes, AI-generated images, cloned audio, and synthetic video.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 900
CELERY_TASK_SOFT_TIME_LIMIT = 720

from PIL import Image as _PILImage

_PILImage.MAX_IMAGE_PIXELS = 64_000_000

MAX_UPLOAD_SIZE = 500 * 1024 * 1024
ALLOWED_MIME_TYPES = [
    "image/jpeg", "image/png", "image/webp",
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm",
    "audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/flac", "audio/mp4",
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
TINEYE_API_KEY = os.environ.get("TINEYE_API_KEY", "")
GOOGLE_VISION_KEY = os.environ.get("GOOGLE_VISION_KEY", "")
GOOGLE_FACT_CHECK_KEY = os.environ.get("GOOGLE_FACT_CHECK_KEY", "")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

REFRESH_COOKIE_NAME = "prooflayer_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth/"
REFRESH_COOKIE_DOMAIN = os.environ.get("REFRESH_COOKIE_DOMAIN", "") or None
REFRESH_COOKIE_SECURE = os.environ.get("REFRESH_COOKIE_SECURE", "true").lower() == "true"
REFRESH_COOKIE_SAMESITE = os.environ.get("REFRESH_COOKIE_SAMESITE", "Lax")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "ProofLayer <noreply@prooflayer.cloud>")
_RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
_EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
if _RESEND_API_KEY:
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    ANYMAIL = {"RESEND_API_KEY": _RESEND_API_KEY}
    INSTALLED_APPS = INSTALLED_APPS + ["anymail"]
    EMAIL_MODE = "resend"
elif _EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = _EMAIL_HOST
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
    EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").lower() == "true"
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_MODE = "smtp"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    EMAIL_MODE = "console"
EMAIL_CONFIGURED = EMAIL_MODE != "console"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
PASSWORD_RESET_TIMEOUT = 60 * 60
PUBLIC_API_URL = (os.environ.get("PUBLIC_API_URL") or os.environ.get("VITE_API_URL") or "http://localhost:8000/api/v1").rstrip("/")

PADDLE_API_KEY = os.environ.get("PADDLE_API_KEY", "")
PADDLE_WEBHOOK_SECRET = os.environ.get("PADDLE_WEBHOOK_SECRET", "")
PADDLE_ENV = "sandbox" if os.environ.get("PADDLE_ENV", "live").strip().lower() == "sandbox" else "live"
PADDLE_API_BASE = "https://sandbox-api.paddle.com" if PADDLE_ENV == "sandbox" else "https://api.paddle.com"
PADDLE_CLIENT_TOKEN = os.environ.get("PADDLE_CLIENT_TOKEN", "")
PERSONAL_FILE_RETENTION_DAYS = int(os.environ.get("PERSONAL_FILE_RETENTION_DAYS", "90"))
TERMS_VERSION = "2026-10-13"

SEARXNG_URL = os.environ.get("SEARXNG_URL", "")
BRAVE_SEARCH_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")
PLAGIARISM_SEARCH_PROVIDERS = [p.strip() for p in os.environ.get("PLAGIARISM_SEARCH_PROVIDERS", "searxng,brave,ddg").split(",") if p.strip()]
PLAGIARISM_WEB_ENABLED = os.environ.get("PLAGIARISM_WEB_ENABLED", "1") == "1"
PLAGIARISM_WEB_QUERIES = int(os.environ.get("PLAGIARISM_WEB_QUERIES", "8"))
PLAGIARISM_WEB_PAGES = int(os.environ.get("PLAGIARISM_WEB_PAGES", "12"))
PLAGIARISM_EMBED_MODEL = os.environ.get("PLAGIARISM_EMBED_MODEL", "intfloat/multilingual-e5-small")

PADDLE_PRO_PRICE_ID = os.environ.get("PADDLE_PRO_PRICE_ID", "")
PADDLE_PRICE_IDS = {
    f"{plan}:{interval}": os.environ.get(f"PADDLE_PRICE_{plan.upper()}_{interval.upper()}", "")
    for plan in ("pro", "education", "university", "enterprise")
    for interval in ("month", "year")
}
PADDLE_PRICE_IDS["pro:month"] = PADDLE_PRICE_IDS["pro:month"] or PADDLE_PRO_PRICE_ID

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = os.environ.get("SENTRY_ENVIRONMENT", "production")
SENTRY_RELEASE = os.environ.get("SENTRY_RELEASE", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        release=SENTRY_RELEASE or None,
        integrations=[DjangoIntegration(), CeleryIntegration(), RedisIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.0,
        send_default_pii=False,
        attach_stacktrace=True,
    )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "urllib3": {"level": "WARNING"},
        "boto3": {"level": "WARNING"},
        "botocore": {"level": "WARNING"},
        "s3transfer": {"level": "WARNING"},
        "weasyprint": {"level": "ERROR"},
        "fontTools": {"level": "ERROR"},
    },
}

DATABASES = {}

UNFOLD = {
    "SITE_TITLE": "ProofLayer Admin",
    "SITE_HEADER": "ProofLayer",
    "SITE_URL": "/",
    "SITE_SYMBOL": "verified",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "COLORS": {
        "font": {
            "subtle-light": "107 114 128",
            "subtle-dark": "156 163 175",
            "default-light": "75 85 99",
            "default-dark": "209 213 219",
            "important-light": "17 24 39",
            "important-dark": "243 244 246",
        },
        "primary": {
            "50": "240 239 255",
            "100": "220 218 255",
            "200": "189 185 255",
            "300": "152 145 255",
            "400": "123 108 246",
            "500": "99 82 234",
            "600": "83 62 220",
            "700": "68 48 190",
            "800": "55 38 156",
            "900": "44 30 124",
            "950": "26 16 80",
        },
    },
    "DASHBOARD_CALLBACK": "common.dashboard.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "items": [
                    {"title": "Dashboard", "icon": "dashboard", "link": reverse_lazy("admin:index")},
                ],
            },
            {
                "title": "Detection",
                "collapsible": True,
                "items": [
                    {"title": "Analyzers", "icon": "tune", "link": reverse_lazy("admin:analyzers_analyzerconfig_changelist")},
                    {"title": "Analysis results", "icon": "analytics", "link": reverse_lazy("admin:analyzers_analysisresult_changelist")},
                    {
                        "title": "Retrain runs",
                        "icon": "model_training",
                        "link": reverse_lazy("admin:analyzers_retrainrun_changelist"),
                        "permission": "common.dashboard.is_superuser",
                    },
                    {"title": "Training samples", "icon": "dataset", "link": reverse_lazy("admin:analyzers_trainingsample_changelist")},
                    {"title": "Known fakes", "icon": "block", "link": reverse_lazy("admin:content_knownfakehash_changelist")},
                ],
            },
            {
                "title": "Content",
                "collapsible": True,
                "items": [
                    {
                        "title": "Submissions",
                        "icon": "folder_open",
                        "link": reverse_lazy("admin:content_submission_changelist"),
                        "badge": "common.dashboard.review_queue_badge",
                    },
                    {
                        "title": "Objections",
                        "icon": "gavel",
                        "link": reverse_lazy("admin:content_verdictobjection_changelist"),
                        "badge": "common.dashboard.open_objections_badge",
                    },
                    {"title": "Verdict overrides", "icon": "rule", "link": reverse_lazy("admin:content_verdictoverride_changelist")},
                    {"title": "Abuse reports", "icon": "flag", "link": reverse_lazy("admin:reports_report_changelist")},
                    {"title": "Plagiarism reports", "icon": "content_copy", "link": reverse_lazy("admin:plagiarism_plagiarismreport_changelist")},
                    {"title": "Provenance", "icon": "travel_explore", "link": reverse_lazy("admin:provenance_provenanceresult_changelist")},
                    {"title": "Votes", "icon": "how_to_vote", "link": reverse_lazy("admin:crowdsource_vote_changelist")},
                ],
            },
            {
                "title": "Classroom",
                "collapsible": True,
                "items": [
                    {"title": "Organizations", "icon": "corporate_fare", "link": reverse_lazy("admin:classroom_organization_changelist")},
                    {"title": "Organization members", "icon": "badge", "link": reverse_lazy("admin:classroom_orgmember_changelist")},
                    {"title": "Classes", "icon": "school", "link": reverse_lazy("admin:classroom_classroom_changelist")},
                    {"title": "Students", "icon": "groups", "link": reverse_lazy("admin:classroom_membership_changelist")},
                    {"title": "Shadow sets", "icon": "blur_on", "link": reverse_lazy("admin:classroom_shadowset_changelist")},
                ],
            },
            {
                "title": "Users & billing",
                "collapsible": True,
                "items": [
                    {"title": "Users", "icon": "person", "link": reverse_lazy("admin:users_user_changelist")},
                    {"title": "Subscriptions", "icon": "credit_card", "link": reverse_lazy("admin:billing_subscription_changelist")},
                    {"title": "API keys", "icon": "key", "link": reverse_lazy("admin:users_apikey_changelist")},
                    {"title": "Email log", "icon": "mail", "link": reverse_lazy("admin:users_emaillog_changelist")},
                ],
            },
            {
                "title": "System",
                "collapsible": True,
                "items": [
                    {"title": "Feedback", "icon": "feedback", "link": reverse_lazy("admin:api_feedback_changelist")},
                    {"title": "Roadmap", "icon": "map", "link": reverse_lazy("admin:api_roadmapitem_changelist")},
                    {
                        "title": "Groups",
                        "icon": "admin_panel_settings",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                        "permission": "common.dashboard.is_superuser",
                    },
                ],
            },
        ],
    },
}
