import base64
from pathlib import Path

from django.core.management.base import BaseCommand

from content.pdf import _members
from factcheck.pdf import build_factcheck_context
from reports.copy import COPY, VERDICT_TONE, tone_set
from reports.render import render_html, render_pdf, shared_context


class _Analyzer:
    def __init__(self, name):
        self.name = name


class _Result:
    def __init__(self, name, verdict, confidence):
        self.analyzer = _Analyzer(name)
        self.verdict = verdict
        self.confidence = confidence


SAMPLE_VOTES = [
    ("custom_detector", "fake", 0.94),
    ("community_forensics", "fake", 0.88),
    ("clip_probe", "suspicious", 0.71),
    ("ai_detector", "suspicious", 0.64),
    ("llm_vision", "inconclusive", 0.0),
    ("metadata", "suspicious", 0.55),
    ("ela", "authentic", 0.62),
]

SAMPLE_TEXT_VOTES = [
    ("text_classifier", "fake", 0.91),
    ("text_evasion", "inconclusive", 0.0),
    ("text_grade_fit", "suspicious", 0.67),
    ("text_style", "suspicious", 0.58),
    ("text_citations", "authentic", 0.8),
]

SAMPLE_ESSAY = {
    "ru": "Индустриализация в СССР стала комплексным процессом трансформации экономической парадигмы. В рамках данного процесса осуществлялась декомпозиция аграрного уклада и формирование индустриального базиса, что обусловило фундаментальные изменения социальной структуры общества. Следует подчеркнуть, что подобная модернизация носила многоаспектный характер...",
    "en": "Industrialization in the USSR was a multifaceted process that transformed the economic paradigm. It involved the decomposition of the agrarian order and the formation of an industrial base, which brought fundamental shifts in the social structure. It is important to note that this modernization was comprehensive in nature...",
}

SAMPLE_FACTCHECK = {
    "overall_verdict": "mixed",
    "claims": [
        {"claim": "The Eiffel Tower was completed in 1889.", "assessment": "likely_true", "confidence": 0.93, "explanation": "Matches the encyclopedia entry for the tower.", "wikipedia": {"title": "Eiffel Tower", "url": "https://en.wikipedia.org/wiki/Eiffel_Tower"}},
        {"claim": "It is the tallest structure in Europe.", "assessment": "likely_false", "confidence": 0.81, "explanation": "Several European structures are taller, for example the Ostankino Tower.", "sources": [{"title": "List of tallest structures in Europe", "url": "https://en.wikipedia.org/wiki/List_of_tallest_structures_in_Europe"}]},
        {"claim": "About seven million people visit it every year.", "assessment": "uncertain", "confidence": 0.52, "explanation": "Recent figures vary between 5.8 and 7 million depending on the year."},
    ],
    "entities": [{"text": "Eiffel Tower"}, {"text": "Europe"}, {"text": "Paris"}],
}


def _image_uri(path: Path) -> str:
    if not path.is_file():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


def sample_submission_context(lang: str, kind: str, image: Path | None) -> dict:
    c = COPY[lang]
    verdict = "likely_fake" if kind == "image" else "needs_review"
    votes = SAMPLE_VOTES if kind == "image" else SAMPLE_TEXT_VOTES
    details = [
        [(c["student"], "Ольга Смирнова" if lang == "ru" else "Olga Smirnova"), (c["classroom"], "9Б" if lang == "ru" else "9B"), (c["handed_in"], "14.10.2026" if lang == "ru" else "Oct 14, 2026")],
        [(c["file"], "IMG_4232.jpg" if kind == "image" else "essay-history.docx"), (c["type"], "Картинка · JPEG" if lang == "ru" and kind == "image" else "Picture · JPEG" if kind == "image" else ("Документ · DOCX" if lang == "ru" else "Document · DOCX")), (c["size"], "2.4 MB" if kind == "image" else "38 KB")],
    ]
    originality = None
    if kind == "text":
        originality = {
            "pct": 72,
            "tone": tone_set("amber")["tone"],
            "matched_line": c["matched"].format(matched=1180, total=4210),
            "scope": c["web_on"],
            "sources": [
                {"title": "Индустриализация в СССР · Википедия", "url": "https://ru.wikipedia.org/wiki/Индустриализация_в_СССР", "share": 18.4},
                {"title": c["internal_source"], "url": "", "share": 9.6},
            ],
        }
    return {
        **shared_context(lang, c["report"], "7A3F2C91"),
        **tone_set(VERDICT_TONE[verdict]),
        "badge": c["in_short"],
        "headline": c["plain"]["teacher"][verdict],
        "meaning": c["meaning"][verdict],
        "detector_line": c["detector_count"].format(fake=4, total=5) if kind == "image" else "",
        "next_step": c["next_step"],
        "note": c["class_note"],
        "known_fake": False,
        "thumbnail": _image_uri(image) if image and kind == "image" else "",
        "excerpt": SAMPLE_ESSAY[lang] if kind == "text" else "",
        "checks": [],
        "show_traces": kind == "image",
        "traces": [],
        "members": _members([_Result(*v) for v in votes], lang, image=kind == "image"),
        "passages": [
            {"text": SAMPLE_ESSAY[lang], "pct": 91, **tone_set("blood")},
            {"text": SAMPLE_ESSAY[lang][:180] + "…", "pct": 58, **tone_set("amber")},
        ] if kind == "text" else [],
        "originality": originality,
        "provenance": [{"title": c["where"]["visible"].format(what=c["where"]["same"], who="Полина Новикова, 9Б, 16.10.2026" if lang == "ru" else "Polina Novikova, 9B, Oct 16, 2026"), "url": "", "similarity": None}] if kind == "image" else [],
        "claims": [],
        "details": details,
        "technical": "SHA-256 7a3f2c91e04b5d18…b91d4e07 · Tribunal 1.10.1",
        "result_url": "https://classroom.prooflayer.cloud/results/7a3f2c91",
    }


class Command(BaseCommand):
    help = "Render sample PDF reports (no database needed) for a visual check"

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True)
        parser.add_argument("--image", default="")
        parser.add_argument("--html", action="store_true")

    def handle(self, *args, **options):
        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)
        image = Path(options["image"]) if options["image"] else None
        jobs = []
        for lang in ("ru", "en"):
            for kind in ("image", "text"):
                jobs.append((f"report-{kind}.{lang}", "content/report.html", sample_submission_context(lang, kind, image)))
            jobs.append((f"factcheck.{lang}", "factcheck/report.html", build_factcheck_context(SAMPLE_FACTCHECK, SAMPLE_ESSAY["en"], lang)))
        for name, template, context in jobs:
            if options["html"]:
                (out / f"{name}.html").write_text(render_html(template, context))
            path = out / f"{name}.pdf"
            path.write_bytes(render_pdf(template, context))
            self.stdout.write(str(path))
