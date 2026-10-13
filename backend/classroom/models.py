import secrets
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction

JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
JOIN_CODE_LENGTH = 8


def new_join_code() -> str:
    return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))


class Classroom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_classrooms")
    organization = models.ForeignKey(
        "Organization", on_delete=models.CASCADE, null=True, blank=True, related_name="classrooms",
    )
    name = models.CharField(max_length=120)
    level = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(17)],
        help_text="1-11 school year, 12-17 university year 1-6",
    )
    join_code = models.CharField(max_length=JOIN_CODE_LENGTH, unique=True)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "classrooms"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.owner_id})"

    def rotate_code(self, attempts: int = 5) -> str:
        for _ in range(attempts):
            self.join_code = new_join_code()
            try:
                with transaction.atomic():
                    self.save(update_fields=["join_code"])
                return self.join_code
            except IntegrityError:
                continue
        raise RuntimeError("could not allocate a unique join code")

    @property
    def billing_owner(self):
        """Who pays for uploads into this class: the school's owner, else the teacher."""
        return self.organization.owner if self.organization_id else self.owner

    @classmethod
    def create_for(cls, owner, name: str, organization=None, level: int | None = None, attempts: int = 5) -> "Classroom":
        for _ in range(attempts):
            try:
                with transaction.atomic():
                    return cls.objects.create(
                        owner=owner, name=name, organization=organization, level=level, join_code=new_join_code(),
                    )
            except IntegrityError:
                continue
        raise RuntimeError("could not allocate a unique join code")


class Membership(models.Model):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="classroom_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "classroom_memberships"
        unique_together = [("classroom", "user")]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user_id} in {self.classroom_id}"


SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$"
RESERVED_SLUGS = frozenset({
    "api", "admin", "app", "assets", "c", "classroom", "classes", "dashboard", "join", "login",
    "logout", "new", "orgs", "pricing", "register", "results", "settings", "static", "status",
    "upload", "verify-email", "www",
})


class Organization(models.Model):
    """A school or teaching organisation: the unit that pays (Education plan) and owns classes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=40, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_organizations")
    teacher_code = models.CharField(max_length=JOIN_CODE_LENGTH, unique=True)
    web_search_enabled = models.BooleanField(
        default=False,
        help_text="Send up to 8 sentences of a class work to external search engines for the originality check",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "classroom_organizations"
        ordering = ["name"]

    def __str__(self):
        return self.slug

    @classmethod
    def create_for(cls, owner, name: str, slug: str, attempts: int = 5) -> "Organization":
        for _ in range(attempts):
            try:
                with transaction.atomic():
                    org = cls.objects.create(owner=owner, name=name, slug=slug, teacher_code=new_join_code())
                    OrgMember.objects.create(organization=org, user=owner, role=OrgMember.Role.ADMIN)
                    return org
            except IntegrityError:
                if cls.objects.filter(slug=slug).exists():
                    raise
                continue
        raise RuntimeError("could not allocate a unique teacher code")

    def rotate_teacher_code(self, attempts: int = 5) -> str:
        for _ in range(attempts):
            self.teacher_code = new_join_code()
            try:
                with transaction.atomic():
                    self.save(update_fields=["teacher_code"])
                return self.teacher_code
            except IntegrityError:
                continue
        raise RuntimeError("could not allocate a unique teacher code")


class OrgMember(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        TEACHER = "teacher", "Teacher"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="org_memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.TEACHER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "classroom_org_members"
        unique_together = [("organization", "user")]
        ordering = ["joined_at"]
