import factory

from crowdsource.models import Vote
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory


class VoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Vote

    user = factory.SubFactory(UserFactory)
    submission = factory.SubFactory(SubmissionFactory)
    value = Vote.Value.REAL
