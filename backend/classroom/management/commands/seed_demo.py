import json
import secrets
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from billing.models import Subscription, get_or_create_subscription
from classroom.models import Classroom, Membership, Organization, OrgMember, ShadowAnswer, ShadowSet
from classroom.shadow import sentence_vectors
from content.models import OBJECTION_ANSWER_BUSINESS_DAYS, Batch, Submission, VerdictObjection, add_business_days
from content.objections import apply_decision
from content.tasks import process_submission
from users.models import User

DATA = Path(__file__).resolve().parents[2] / "demo" / "demo_data.json"
DEMO_DOMAIN = "demo.prooflayer.cloud"
POLL_SECONDS = 3
DONE = {Submission.Status.COMPLETED, Submission.Status.FAILED}
ASSET_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
}


class Command(BaseCommand):
    help = "Create demo schools, teachers, students and analysed class work for presentations"

    def add_arguments(self, parser):
        parser.add_argument("--data", default=str(DATA))
        parser.add_argument("--reset", action="store_true", help=f"delete existing @{DEMO_DOMAIN} users and their schools first")
        parser.add_argument("--timeout", type=int, default=600, help="seconds to wait for each work to be analysed")
        parser.add_argument("--no-wait", action="store_true", help="queue analysis without waiting")
        parser.add_argument("--orgs", nargs="*", default=[], help="only these organization slugs")

    def handle(self, *args, **opts):
        data_path = Path(opts["data"])
        data = json.loads(data_path.read_text(encoding="utf-8"))
        self.assets = data_path.parent / "assets"
        if opts["orgs"]:
            data["organizations"] = [o for o in data["organizations"] if o["slug"] in opts["orgs"]]
            if not data["organizations"]:
                raise CommandError(f"no organization matches {opts['orgs']}")
        if opts["reset"]:
            self._reset()
        elif User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").exists():
            raise CommandError("demo users already exist, run with --reset to recreate them")
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
                for student_data in class_data["students"]:
                    student, password = self._user(student_data)
                    passwords[student.email] = password
                    Membership.objects.create(classroom=classroom, user=student)
                    works += [(work["days_ago"], student, classroom, teacher, work) for work in student_data["works"]]
                works += [(work["days_ago"], teacher, classroom, teacher, work) for work in class_data.get("teacher_checks", [])]
        works.sort(key=lambda w: -w[0])
        for days_ago, student, classroom, teacher, work in works:
            submission = self._submit(student, classroom, work, days_ago, teacher)
            if not opts["no_wait"]:
                self._wait(submission, opts["timeout"])
            if work.get("objection"):
                self._object(submission, student, teacher, work["objection"])
        self.stdout.write("\nDemo accounts (shown once):")
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
        password = secrets.token_urlsafe(9)
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
        if asset:
            body = (self.assets / asset).read_bytes()
            mime = ASSET_MIME[Path(asset).suffix.lower()]
        else:
            body = work["text"].encode("utf-8")
            mime = "text/plain"
        submission = Submission.objects.create(
            user=student,
            file=ContentFile(body, name=name),
            original_filename=name,
            mime_type=mime,
            file_size=len(body),
            classroom=classroom,
            uploaded_by=teacher if work.get("uploaded_by_teacher") else None,
            batch=self._batch(teacher, classroom, work.get("batch")),
        )
        Submission.objects.filter(pk=submission.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        process_submission.delay(str(submission.id))
        self.stdout.write(f"queued {student.username}: {name}")
        return submission

    def _batch(self, teacher: User, classroom: Classroom, name: str | None) -> Batch | None:
        if not name:
            return None
        key = (classroom.pk, name)
        if key not in self.batches:
            self.batches[key] = Batch.objects.create(user=teacher, name=name, classroom=classroom)
        return self.batches[key]

    def _object(self, submission: Submission, student: User, teacher: User, spec: dict):
        objection = VerdictObjection(submission=submission, author=student, reason=spec["reason"])
        if spec.get("response"):
            submission.refresh_from_db(fields=["final_verdict"])
            objection.status = VerdictObjection.Status.ANSWERED
            objection.decision = spec.get("decision", VerdictObjection.Decision.UPHELD)
            objection.response = spec["response"]
            objection.responded_by = teacher
            objection.responded_at = timezone.now()
            apply_decision(objection, teacher)
        objection.save()
        if spec.get("days_ago"):
            filed = timezone.now() - timedelta(days=spec["days_ago"])
            due = add_business_days(timezone.localtime(filed), OBJECTION_ANSWER_BUSINESS_DAYS)
            answered = filed + timedelta(days=1) if objection.responded_at else None
            VerdictObjection.objects.filter(pk=objection.pk).update(created_at=filed, due_at=due, responded_at=answered)

    def _wait(self, submission: Submission, timeout: int):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            submission.refresh_from_db(fields=["status", "final_verdict"])
            if submission.status in DONE:
                self.stdout.write(f"  -> {submission.status} {submission.final_verdict}")
                return
            time.sleep(POLL_SECONDS)
        self.stdout.write(self.style.WARNING(f"  -> still {submission.status} after {timeout}s, moving on"))
