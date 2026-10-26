from unittest.mock import patch

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail as outbox
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from billing.models import Subscription, get_or_create_subscription
from classroom.models import Classroom, Membership, Organization, OrgMember
from common.demo import DEMO_DOMAIN, is_demo_email
from users.models import ApiKey, EmailChangeToken, User

from .factories import UserFactory

PASSWORD = "testpass123"


@pytest.fixture(autouse=True)
def _locmem_mail(settings):
    settings.EMAIL_CONFIGURED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    outbox.outbox = []


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _edu(email):
    user = UserFactory(email=email, is_verified=True)
    sub = get_or_create_subscription(user)
    sub.tier = Subscription.Tier.EDUCATION
    sub.save(update_fields=["tier"])
    return user


def _demo_teacher():
    return _edu(f"teacher@{DEMO_DOMAIN}")


def _locked(response):
    assert response.status_code == 403
    assert response.data["code"] == "demo_account"


def test_demo_address_detection():
    assert is_demo_email(f"Someone@{DEMO_DOMAIN.upper()} ")
    assert not is_demo_email(f"someone@not{DEMO_DOMAIN}")
    assert not is_demo_email("someone@example.com")
    assert not is_demo_email(None)


@pytest.mark.django_db
class TestDemoAccountLocks:
    def test_payload_marks_demo_accounts(self):
        assert _client(_demo_teacher()).get(reverse("me")).data["is_demo"] is True

    def test_cannot_change_email(self):
        user = _demo_teacher()
        _locked(_client(user).post(reverse("email-change"), {"new_email": "mine@example.com", "password": PASSWORD}, format="json"))
        _locked(_client(user).post(reverse("email-change-resend")))
        assert not EmailChangeToken.objects.exists()
        assert outbox.outbox == []

    def test_confirm_refuses_a_demo_token(self):
        user = _demo_teacher()
        change = EmailChangeToken.objects.create(user=user, new_email="mine@example.com")
        _locked(_client().post(reverse("email-change-confirm"), {"token": change.token}, format="json"))
        user.refresh_from_db()
        assert user.email == f"teacher@{DEMO_DOMAIN}"

    def test_cannot_delete_the_account(self):
        user = _demo_teacher()
        _locked(_client(user).delete(reverse("me"), {"password": PASSWORD}, format="json"))
        assert User.objects.filter(pk=user.pk).exists()

    def test_cannot_request_a_password_reset(self):
        _demo_teacher()
        with patch("users.views.send_password_reset_email.delay") as delay:
            response = _client().post(reverse("password-reset"), {"email": f"Teacher@{DEMO_DOMAIN}"}, format="json")
        _locked(response)
        delay.assert_not_called()

    def test_cannot_use_a_password_reset_link(self):
        user = _demo_teacher()
        response = _client().post(
            reverse("password-reset-confirm"),
            {"uid": urlsafe_base64_encode(force_bytes(user.pk)), "token": default_token_generator.make_token(user), "password": "Fresh-Pass-2026"},
            format="json",
        )
        _locked(response)
        user.refresh_from_db()
        assert user.check_password(PASSWORD)

    def test_api_keys_can_be_listed_but_not_created_or_revoked(self):
        user = _demo_teacher()
        key, _ = ApiKey.issue(user, "seeded")
        client = _client(user)
        assert client.get(reverse("api-key-list")).status_code == 200
        _locked(client.post(reverse("api-key-list"), {"name": "mine"}, format="json"))
        _locked(client.patch(reverse("api-key-detail", args=[key.id]), {"name": "renamed"}, format="json"))
        _locked(client.delete(reverse("api-key-detail", args=[key.id])))
        key.refresh_from_db()
        assert key.revoked_at is None
        assert key.name == "seeded"
        assert ApiKey.objects.filter(user=user).count() == 1

    def test_billing_checkout_and_portal_are_off(self):
        client = _client(_demo_teacher())
        _locked(client.post(reverse("create-checkout"), {"plan": "pro", "interval": "month"}, format="json"))
        _locked(client.post(reverse("customer-portal")))

    def test_school_cannot_be_deleted_or_stripped(self):
        owner = _demo_teacher()
        org = Organization.create_for(owner, "Demo Lyceum", "demo-lyceum")
        colleague = UserFactory(email=f"colleague@{DEMO_DOMAIN}", is_verified=True)
        OrgMember.objects.create(organization=org, user=colleague, role=OrgMember.Role.TEACHER)
        client = _client(owner)
        code = org.teacher_code
        _locked(client.delete(reverse("org-detail", args=[org.slug]), {"password": PASSWORD}, format="json"))
        _locked(client.post(reverse("org-rotate-code", args=[org.slug])))
        _locked(client.delete(reverse("org-teacher-detail", args=[org.slug, colleague.id])))
        org.refresh_from_db()
        assert org.teacher_code == code
        assert OrgMember.objects.filter(organization=org, user=colleague).exists()

    def test_real_accounts_still_manage_their_school(self):
        owner = _edu("owner@example.com")
        org = Organization.create_for(owner, "Lyceum", "real-lyceum")
        assert _client(owner).post(reverse("org-rotate-code", args=[org.slug])).status_code == 200


@pytest.mark.django_db
class TestDemoAndRealAccountsDoNotMix:
    def test_real_teacher_cannot_join_a_demo_school(self):
        org = Organization.create_for(_demo_teacher(), "Demo Lyceum", "demo-lyceum")
        outsider = UserFactory(is_verified=True)
        response = _client(outsider).post(reverse("org-join-teacher", args=[org.slug]), {"code": org.teacher_code}, format="json")
        assert response.status_code == 403
        assert response.data["code"] == "demo_school"
        assert not OrgMember.objects.filter(user=outsider).exists()

    def test_demo_teacher_cannot_join_a_real_school(self):
        org = Organization.create_for(_edu("owner@example.com"), "Lyceum", "real-lyceum")
        demo = UserFactory(email=f"guest@{DEMO_DOMAIN}", is_verified=True)
        _locked(_client(demo).post(reverse("org-join-teacher", args=[org.slug]), {"code": org.teacher_code}, format="json"))

    def test_demo_colleague_can_join_the_demo_school(self):
        org = Organization.create_for(_demo_teacher(), "Demo Lyceum", "demo-lyceum")
        colleague = UserFactory(email=f"colleague@{DEMO_DOMAIN}", is_verified=True)
        response = _client(colleague).post(reverse("org-join-teacher", args=[org.slug]), {"code": org.teacher_code}, format="json")
        assert response.status_code == 201

    def test_real_student_cannot_join_a_demo_class(self):
        classroom = Classroom.create_for(_demo_teacher(), "8A")
        student = UserFactory(is_verified=True)
        response = _client(student).post(reverse("classroom-join"), {"code": classroom.join_code}, format="json")
        assert response.status_code == 403
        assert response.data["code"] == "demo_school"
        assert not Membership.objects.filter(user=student).exists()

    def test_demo_student_cannot_join_a_real_class(self):
        classroom = Classroom.create_for(_edu("teacher@example.com"), "8A")
        demo = UserFactory(email=f"pupil@{DEMO_DOMAIN}", is_verified=True)
        _locked(_client(demo).post(reverse("classroom-join"), {"code": classroom.join_code}, format="json"))
        assert not Membership.objects.filter(user=demo).exists()

    def test_real_classes_stay_open_to_real_students(self):
        classroom = Classroom.create_for(_edu("teacher@example.com"), "8A")
        response = _client(UserFactory(is_verified=True)).post(reverse("classroom-join"), {"code": classroom.join_code}, format="json")
        assert response.status_code == 201
