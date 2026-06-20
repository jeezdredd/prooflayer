import pytest
from rest_framework.test import APIRequestFactory

from common.throttling import StaffBypassAnonRateThrottle, StaffBypassUserRateThrottle
from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestStaffBypassThrottle:
    def setup_method(self):
        self.factory = APIRequestFactory()

    def test_staff_user_bypasses(self):
        throttle = StaffBypassUserRateThrottle()
        request = self.factory.get("/")
        request.user = UserFactory(is_staff=True)
        assert throttle.allow_request(request, None) is True

    def test_superuser_bypasses(self):
        throttle = StaffBypassUserRateThrottle()
        request = self.factory.get("/")
        request.user = UserFactory(is_superuser=True)
        assert throttle.allow_request(request, None) is True

    def test_anon_throttle_staff_bypasses(self):
        throttle = StaffBypassAnonRateThrottle()
        request = self.factory.get("/")
        request.user = UserFactory(is_staff=True)
        assert throttle.allow_request(request, None) is True

    def test_regular_user_respects_limit(self):
        request = self.factory.get("/")
        request.user = UserFactory()

        first = StaffBypassUserRateThrottle()
        first.num_requests = 1
        first.duration = 3600
        assert first.allow_request(request, None) is True

        second = StaffBypassUserRateThrottle()
        second.num_requests = 1
        second.duration = 3600
        assert second.allow_request(request, None) is False
