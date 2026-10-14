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
from classroom.models import Classroom, Membership, Organization, ShadowAnswer, ShadowSet
from classroom.shadow import sentence_vectors
from content.models import Submission
from content.tasks import process_submission
from users.models import User

DATA = Path(__file__).resolve().parents[2] / "demo" / "demo_data.json"
DEMO_DOMAIN = "demo.prooflayer.cloud"
POLL_SECONDS = 3
DONE = {Submission.Status.COMPLETED, Submission.Status.FAILED}


class Command(BaseCommand):
    help = "Create demo schools, teachers, students and analysed class work for presentations"

    def add_arguments(self, parser):
        parser.add_argument("--data", default=str(DATA))
        parser.add_argument("--reset", action="store_true", help=f"delete existing @{DEMO_DOMAIN} users and their schools first")
        parser.add_argument("--timeout", type=int, default=600, help="seconds to wait for each work to be analysed")
        parser.add_argument("--no-wait", action="store_true", help="queue analysis without waiting")

    def handle(self, *args, **opts):
        data = json.loads(Path(opts["data"]).read_text(encoding="utf-8"))
        if opts["reset"]:
            self._reset()
        elif User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").exists():
            raise CommandError("demo users already exist, run with --reset to recreate them")
        passwords = {}
        works = []
        for org_data in data["organizations"]:
            teacher, password = self._user(org_data["teacher"], teacher=True)
            passwords[teacher.email] = password
            org = Organization.create_for(teacher, org_data["name"], org_data["slug"])
            for class_data in org_data["classes"]:
                classroom = Classroom.create_for(teacher, class_data["name"], organization=org, level=class_data.get("level"))
                if class_data.get("shadow"):
                    self._shadow(classroom, teacher, class_data["shadow"])
                for student_data in class_data["students"]:
                    student, password = self._user(student_data)
                    passwords[student.email] = password
                    Membership.objects.create(classroom=classroom, user=student)
                    works += [(work["days_ago"], student, classroom, work) for work in student_data["works"]]
        works.sort(key=lambda w: -w[0])
        for days_ago, student, classroom, work in works:
            submission = self._submit(student, classroom, work, days_ago)
            if not opts["no_wait"]:
                self._wait(submission, opts["timeout"])
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

    def _submit(self, student: User, classroom: Classroom, work: dict, days_ago: int) -> Submission:
        body = work["text"].encode("utf-8")
        name = work["filename"]
        submission = Submission.objects.create(
            user=student,
            file=ContentFile(body, name=name),
            original_filename=name,
            mime_type="text/plain",
            file_size=len(body),
            classroom=classroom,
        )
        Submission.objects.filter(pk=submission.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        process_submission.delay(str(submission.id))
        self.stdout.write(f"queued {student.username}: {name}")
        return submission

    def _wait(self, submission: Submission, timeout: int):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            submission.refresh_from_db(fields=["status", "final_verdict"])
            if submission.status in DONE:
                self.stdout.write(f"  -> {submission.status} {submission.final_verdict}")
                return
            time.sleep(POLL_SECONDS)
        self.stdout.write(self.style.WARNING(f"  -> still {submission.status} after {timeout}s, moving on"))
