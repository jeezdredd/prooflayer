import secrets
import uuid

from django.conf import settings
from django.db import IntegrityError, models, transaction

JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
JOIN_CODE_LENGTH = 8


def new_join_code() -> str:
    return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))


class Classroom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_classrooms")
    name = models.CharField(max_length=120)
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

    @classmethod
    def create_for(cls, owner, name: str, attempts: int = 5) -> "Classroom":
        for _ in range(attempts):
            try:
                with transaction.atomic():
                    return cls.objects.create(owner=owner, name=name, join_code=new_join_code())
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
