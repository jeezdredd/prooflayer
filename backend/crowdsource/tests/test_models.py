import pytest
from django.db import IntegrityError

from crowdsource.models import Vote
from .factories import VoteFactory


@pytest.mark.django_db
class TestVoteModel:
    def test_create_vote(self):
        vote = VoteFactory()
        assert vote.value == Vote.Value.REAL
        assert vote.pk is not None

    def test_unique_user_submission(self):
        vote = VoteFactory()
        with pytest.raises(IntegrityError):
            VoteFactory(user=vote.user, submission=vote.submission)

    def test_value_choices(self):
        values = {c.value for c in Vote.Value}
        assert values == {"real", "fake", "uncertain"}
