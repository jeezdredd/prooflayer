import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Max
from django.utils import timezone

from billing.models import Subscription, get_or_create_subscription
from classroom.models import Classroom, Membership, Organization, OrgMember, ShadowAnswer, ShadowSet
from classroom.radar import class_radar
from classroom.serializers import FLAG_ORDER, submission_flags
from classroom.shadow import sentence_vectors
from classroom.views import RADAR_DAYS
from common.demo import DEMO_DOMAIN
from common.documents import DOCUMENT_MIMES
from content.models import (
    OBJECTION_ANSWER_BUSINESS_DAYS,
    Batch,
    Submission,
    VerdictObjection,
    VerdictOverride,
    add_business_days,
)
from content.objections import apply_decision
from content.tasks import process_submission
from plagiarism.models import PlagiarismReport
from users.models import User

DATA = Path(__file__).resolve().parents[2] / "demo" / "demo_data.json"
POLL_SECONDS = 3
DONE = {Submission.Status.COMPLETED, Submission.Status.FAILED}
REPORT_DONE = {PlagiarismReport.Status.DONE, PlagiarismReport.Status.FAILED}
ASSET_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
}
PASSWORD_LENGTH = 12
FRESH_DAYS = 1
EXPECT_KEYS = {"verdict", "flags", "originality", "radar", "ai", "genre", "copied_from"}
AI_BANDS = {"flag", "look", "clear", "short"}
RADAR_MARKS = {"ai", "vocabulary", "style", "pair"}


def demo_password(email: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), email.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")[:PASSWORD_LENGTH]


def password_secret() -> str:
    return os.environ.get("DEMO_PASSWORD_SECRET") or settings.SECRET_KEY


def class_works(org: dict, class_data: dict) -> list[tuple[str, dict]]:
    teachers = {org["teacher"]["username"]: org["teacher"]["email"], **{t["username"]: t["email"] for t in org.get("teachers", [])}}
    teacher = teachers[class_data.get("teacher", org["teacher"]["username"])]
    works = [(student["email"], work) for student in class_data["students"] for work in student["works"]]
    return works + [(teacher, work) for work in class_data.get("teacher_checks", [])]


def is_text_mime(mime: str) -> bool:
    return mime == "text/plain" or mime in DOCUMENT_MIMES


def work_mime(work: dict) -> str:
    asset = work.get("asset")
    return ASSET_MIME[Path(asset).suffix.lower()] if asset else "text/plain"


def check_expect(name: str, expect: dict) -> None:
    unknown = set(expect) - EXPECT_KEYS
    if unknown:
        raise CommandError(f"{name}: unknown expect keys {sorted(unknown)}")
    if "ai" in expect and expect["ai"] not in AI_BANDS:
        raise CommandError(f"{name}: expect.ai must be one of {sorted(AI_BANDS)}")
    if set(expect.get("flags", [])) - set(FLAG_ORDER):
        raise CommandError(f"{name}: unknown flags {sorted(set(expect['flags']) - set(FLAG_ORDER))}")
    if set(expect.get("radar", [])) - RADAR_MARKS:
        raise CommandError(f"{name}: unknown radar marks {sorted(set(expect['radar']) - RADAR_MARKS)}")
    wanted = expect.get("originality")
    if wanted is not None and not (isinstance(wanted, list) and len(wanted) == 2 and wanted[0] <= wanted[1]):
        raise CommandError(f"{name}: expect.originality must be null or [low, high]")


def check_data(data: dict) -> None:
    for org in data["organizations"]:
        for class_data in org["classes"]:
            seen = set()
            for email, work in class_works(org, class_data):
                name = f"{email.split('@')[0]}/{work['filename']}"
                if (email, work["filename"]) in seen:
                    raise CommandError(f"{name}: the same student hands in two works with this file name")
                seen.add((email, work["filename"]))
                spec = work.get("objection") or {}
                if spec.get("days_ago") is not None and spec["days_ago"] > work["days_ago"]:
                    raise CommandError(f"{name}: the objection is dated before the work it objects to")
                if work.get("expect") is not None:
                    check_expect(name, work["expect"])


def compare(expect: dict, actual: dict) -> list[str]:
    problems = []
    if "verdict" in expect and actual["verdict"] not in expect["verdict"]:
        problems.append(f"verdict: expected {'/'.join(expect['verdict'])}, got {actual['verdict']}")
    if "flags" in expect and sorted(expect["flags"], key=FLAG_ORDER.index) != actual["flags"]:
        wanted = ",".join(sorted(expect["flags"], key=FLAG_ORDER.index)) or "none"
        problems.append(f"flags: expected {wanted}, got {','.join(actual['flags']) or 'none'}")
    if "originality" in expect:
        wanted, got = expect["originality"], actual["originality"]
        web = f" (web search: {actual.get('web_status') or 'off'})" if got is not None else ""
        if wanted is None and got is not None:
            problems.append(f"originality: expected no check, got {got:g}")
        elif wanted is not None and (got is None or not wanted[0] <= got <= wanted[1]):
            shown = "no report" if got is None else f"{got:g}"
            problems.append(f"originality: expected {wanted[0]:g}-{wanted[1]:g}, got {shown}{web}")
    if "radar" in expect and sorted(expect["radar"]) != actual["radar"]:
        problems.append(f"radar: expected {','.join(sorted(expect['radar'])) or 'none'}, got {','.join(actual['radar']) or 'none'}")
    return problems


class Command(BaseCommand):
    help = "Create demo schools, teachers, students and analysed class work for presentations"

    def add_arguments(self, parser):
        parser.add_argument("--data", default=str(DATA))
        parser.add_argument("--reset", action="store_true", help=f"delete existing @{DEMO_DOMAIN} users and their schools first")
        parser.add_argument("--timeout", type=int, default=600, help="seconds to wait for each work to be analysed")
        parser.add_argument("--no-wait", action="store_true", help="queue analysis without waiting")
        parser.add_argument("--orgs", nargs="*", default=[], help="only these organization slugs")
        parser.add_argument(
            "--rotate-passwords", action="store_true",
            help="random passwords instead of the ones derived from DEMO_PASSWORD_SECRET (or SECRET_KEY) and the email",
        )
        parser.add_argument(
            "--redate", action="store_true",
            help="move the dates of demo works, objections, batches and AI answers forward so the newest work is a day old; no re-analysis",
        )
        parser.add_argument(
            "--verify", action="store_true",
            help="once every work and originality report is done, compare them with the expect blocks and exit 1 on a mismatch",
        )

    def handle(self, *args, **opts):
        data_path = Path(opts["data"])
        data = json.loads(data_path.read_text(encoding="utf-8"))
        self.assets = data_path.parent / "assets"
        if opts["orgs"]:
            data["organizations"] = [o for o in data["organizations"] if o["slug"] in opts["orgs"]]
            if not data["organizations"]:
                raise CommandError(f"no organization matches {opts['orgs']}")
        check_data(data)
        exists = User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").exists()
        if opts["reset"]:
            self._reset()
            self._seed(data, opts)
        elif not exists:
            if opts["redate"]:
                raise CommandError("there is no demo to redate yet: run seed_demo first")
            self._seed(data, opts)
        elif not (opts["redate"] or opts["verify"]):
            raise CommandError("demo users already exist: --reset recreates them, --redate refreshes their dates, --verify checks them")
        if opts["redate"]:
            self._redate()
        if opts["verify"] and not self._verify(data, opts["timeout"]):
            raise CommandError("the demo does not show what demo_data.json expects")

    def _seed(self, data: dict, opts: dict):
        self.rotate = opts["rotate_passwords"]
        self.secret = password_secret()
        passwords = {}
        works = []
        self.batches = {}
        for org_data in data["organizations"]:
            owner, password = self._user(org_data["teacher"], teacher=True)
            passwords[owner.email] = password
            org = Organization.create_for(owner, org_data["name"], org_data["slug"])
            staff = {owner.username: owner}
            for spec in org_data.get("teachers", []):
                colleague, password = self._user(spec)
                passwords[colleague.email] = password
                OrgMember.objects.create(organization=org, user=colleague, role=OrgMember.Role.TEACHER)
                staff[colleague.username] = colleague
            for class_data in org_data["classes"]:
                teacher = staff[class_data.get("teacher", owner.username)]
                classroom = Classroom.create_for(teacher, class_data["name"], organization=org, level=class_data.get("level"))
                if class_data.get("archived"):
                    Classroom.objects.filter(pk=classroom.pk).update(archived=True)
                if class_data.get("shadow"):
                    self._shadow(classroom, teacher, class_data["shadow"])
                students = {}
                for student_data in class_data["students"]:
                    student, password = self._user(student_data)
                    passwords[student.email] = password
                    Membership.objects.create(classroom=classroom, user=student)
                    students[student.email] = student
                for email, work in class_works(org_data, class_data):
                    works.append((work["days_ago"], students.get(email, teacher), classroom, teacher, work))
        works.sort(key=lambda w: -w[0])
        for days_ago, student, classroom, teacher, work in works:
            submission = self._submit(student, classroom, work, days_ago, teacher)
            if not opts["no_wait"]:
                self._wait(submission, opts["timeout"])
            if work.get("objection"):
                self._object(submission, student, teacher, work["objection"])
        heading = "Demo accounts (random passwords, shown once):" if self.rotate else "Demo accounts:"
        self.stdout.write(f"\n{heading}")
        for email, password in passwords.items():
            self.stdout.write(f"  {email}  {password}")

    def _reset(self):
        users = User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}")
        Organization.objects.filter(owner__in=users).delete()
        Classroom.objects.filter(owner__in=users).delete()
        deleted, _ = users.delete()
        self.stdout.write(f"removed {deleted} demo rows")

    def _user(self, spec: dict, teacher: bool = False) -> tuple[User, str]:
        if not spec["email"].endswith(f"@{DEMO_DOMAIN}"):
            raise CommandError(f"demo emails must end with @{DEMO_DOMAIN}: {spec['email']}")
        password = secrets.token_urlsafe(9) if self.rotate else demo_password(spec["email"], self.secret)
        now = timezone.now()
        user = User.objects.create_user(
            email=spec["email"],
            username=spec["username"],
            password=password,
            first_name=spec.get("first_name", ""),
            last_name=spec.get("last_name", ""),
            is_verified=True,
            is_adult=True,
            age_confirmed_at=now,
            terms_version=settings.TERMS_VERSION,
            terms_accepted_at=now,
        )
        if teacher:
            sub = get_or_create_subscription(user)
            sub.tier = Subscription.Tier.EDUCATION
            sub.save(update_fields=["tier"])
        return user, password

    def _shadow(self, classroom: Classroom, teacher: User, spec: dict):
        shadow = ShadowSet.objects.create(
            classroom=classroom,
            created_by=teacher,
            prompt=spec["prompt"],
            language=spec["language"],
            target=len(spec["answers"]),
            status=ShadowSet.Status.DONE,
        )
        for answer in spec["answers"]:
            ShadowAnswer.objects.create(shadow_set=shadow, text=answer["text"], variant=answer["variant"], vectors=sentence_vectors(answer["text"]))
        ShadowSet.objects.filter(pk=shadow.pk).update(created_at=timezone.now() - timedelta(days=spec.get("days_ago", 30)))

    def _submit(self, student: User, classroom: Classroom, work: dict, days_ago: int, teacher: User) -> Submission:
        name = work["filename"]
        asset = work.get("asset")
        body = (self.assets / asset).read_bytes() if asset else work["text"].encode("utf-8")
        handed_in = timezone.now() - timedelta(days=days_ago)
        uploaded_by = teacher if work.get("uploaded_by_teacher") and student != teacher else None
        submission = Submission.objects.create(
            user=student,
            file=ContentFile(body, name=name),
            original_filename=name,
            mime_type=work_mime(work),
            file_size=len(body),
            classroom=classroom,
            uploaded_by=uploaded_by,
            batch=self._batch(teacher, classroom, work.get("batch"), handed_in),
        )
        Submission.objects.filter(pk=submission.pk).update(created_at=handed_in)
        submission.created_at = handed_in
        process_submission.delay(str(submission.id))
        self.stdout.write(f"queued {student.username}: {name}")
        return submission

    def _batch(self, teacher: User, classroom: Classroom, name: str | None, handed_in) -> Batch | None:
        if not name:
            return None
        key = (classroom.pk, name)
        if key not in self.batches:
            batch = Batch.objects.create(user=teacher, name=name, classroom=classroom)
            Batch.objects.filter(pk=batch.pk).update(created_at=handed_in)
            self.batches[key] = batch
        return self.batches[key]

    def _object(self, submission: Submission, student: User, teacher: User, spec: dict):
        now = timezone.now()
        objection = VerdictObjection(submission=submission, author=student, reason=spec["reason"])
        if spec.get("days_ago") is not None:
            filed = now - timedelta(days=spec["days_ago"])
        elif spec.get("response"):
            filed = min(submission.created_at + timedelta(days=1), now)
        else:
            filed = now
        answered = None
        if spec.get("response"):
            submission.refresh_from_db(fields=["final_verdict"])
            answered = min(filed + timedelta(days=1), now)
            objection.status = VerdictObjection.Status.ANSWERED
            objection.decision = spec.get("decision", VerdictObjection.Decision.UPHELD)
            objection.response = spec["response"]
            objection.responded_by = teacher
            objection.responded_at = answered
            apply_decision(objection, teacher)
        objection.save()
        due = add_business_days(timezone.localtime(filed), OBJECTION_ANSWER_BUSINESS_DAYS)
        VerdictObjection.objects.filter(pk=objection.pk).update(created_at=filed, due_at=due, responded_at=answered)
        if answered:
            VerdictOverride.objects.filter(submission=submission).update(created_at=answered)

    def _wait(self, submission: Submission, timeout: int):
        deadline = time.monotonic() + timeout
        if self._settle(submission, deadline):
            self.stdout.write(f"  -> {submission.status} {submission.final_verdict}")
        else:
            self.stdout.write(self.style.WARNING(f"  -> still {submission.status} after {timeout}s, moving on"))

    def _settle(self, submission: Submission, deadline: float) -> bool:
        needs_report = is_text_mime(submission.mime_type)
        while True:
            submission.refresh_from_db(fields=["status", "final_verdict"])
            report = PlagiarismReport.objects.filter(submission=submission).values_list("status", flat=True).first()
            if submission.status in DONE and (report in REPORT_DONE if needs_report else True):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(POLL_SECONDS)

    def _redate(self):
        users = User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}")
        works = Submission.objects.filter(user__in=users)
        newest = works.aggregate(newest=Max("created_at"))["newest"]
        if newest is None:
            raise CommandError("there are no demo works to redate")
        days = (timezone.now() - newest).days - FRESH_DAYS
        if days <= 0:
            self.stdout.write("demo dates are already fresh")
            return
        shift = timedelta(days=days)
        ids = list(works.values_list("id", flat=True))
        Submission.objects.filter(id__in=ids).update(created_at=F("created_at") + shift, updated_at=F("updated_at") + shift)
        PlagiarismReport.objects.filter(submission_id__in=ids).update(created_at=F("created_at") + shift, updated_at=F("updated_at") + shift)
        VerdictOverride.objects.filter(submission_id__in=ids).update(created_at=F("created_at") + shift)
        Batch.objects.filter(user__in=users).update(created_at=F("created_at") + shift)
        ShadowSet.objects.filter(classroom__owner__in=users).update(created_at=F("created_at") + shift)
        for objection in VerdictObjection.objects.filter(submission_id__in=ids):
            filed = objection.created_at + shift
            VerdictObjection.objects.filter(pk=objection.pk).update(
                created_at=filed,
                due_at=add_business_days(timezone.localtime(filed), OBJECTION_ANSWER_BUSINESS_DAYS),
                responded_at=objection.responded_at + shift if objection.responded_at else None,
            )
        self.stdout.write(f"moved {len(ids)} demo works and their objections, batches and AI answers forward by {days} days")

    def _verify(self, data: dict, timeout: int) -> bool:
        deadline = time.monotonic() + timeout
        radars = {}
        rows = []
        for org in data["organizations"]:
            for class_data in org["classes"]:
                classroom = Classroom.objects.filter(organization__slug=org["slug"], name=class_data["name"]).first()
                for email, work in class_works(org, class_data):
                    expect = work.get("expect")
                    if expect is None:
                        continue
                    who = email.split("@")[0]
                    submission = None
                    if classroom is not None:
                        submission = (
                            Submission.objects.filter(classroom=classroom, user__email=email, original_filename=work["filename"])
                            .order_by("-created_at").first()
                        )
                    if submission is None:
                        rows.append((who, work["filename"], "-", "-", "-", "-", ["work not found"]))
                        continue
                    self._settle(submission, deadline)
                    actual = self._actual(submission, classroom, radars)
                    rows.append((
                        who, work["filename"], actual["verdict"], ",".join(actual["flags"]) or "-",
                        "-" if actual["originality"] is None else f"{actual['originality']:g}",
                        ",".join(actual["radar"]) or "-", compare(expect, actual),
                    ))
        self._table(rows)
        failed = [r for r in rows if r[6]]
        if failed:
            self.stdout.write(self.style.ERROR(f"{len(failed)} of {len(rows)} works differ from demo_data.json"))
        else:
            self.stdout.write(self.style.SUCCESS(f"all {len(rows)} works show what demo_data.json expects"))
        return not failed

    def _actual(self, submission: Submission, classroom: Classroom, radars: dict) -> dict:
        submission = (
            Submission.objects.select_related("plagiarism_report")
            .prefetch_related("analysis_results__analyzer", "objections")
            .get(pk=submission.pk)
        )
        report = getattr(submission, "plagiarism_report", None)
        done = submission.status == Submission.Status.COMPLETED
        if classroom.pk not in radars:
            radars[classroom.pk] = class_radar(classroom, timezone.now() - timedelta(days=RADAR_DAYS))
        radar = radars[classroom.pk]
        key = str(submission.pk)
        marks = {r["kind"] for j in radar["level_jumps"] if j["submission_id"] == key for r in j["reasons"]}
        if any(key in (p["a"]["submission_id"], p["b"]["submission_id"]) for p in radar["shared_skeletons"]):
            marks.add("pair")
        report_done = report is not None and report.status == PlagiarismReport.Status.DONE
        return {
            "verdict": submission.final_verdict if done else submission.status,
            "flags": submission_flags(submission) if done else [],
            "originality": report.originality if report_done else None,
            "web_status": report.web_status if report_done else None,
            "radar": sorted(marks),
        }

    def _table(self, rows: list[tuple]):
        header = ("who", "work", "verdict", "flags", "orig", "radar", "check")
        lines = [header] + [(*r[:6], "ok" if not r[6] else "; ".join(r[6])) for r in rows]
        widths = [max(len(str(line[i])) for line in lines) for i in range(6)]
        for line in lines:
            cells = [str(line[i]).ljust(widths[i]) for i in range(6)]
            self.stdout.write("  ".join([*cells, str(line[6])]))
