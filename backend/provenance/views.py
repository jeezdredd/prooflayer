from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from classroom.access import supervised_q, visible_submissions_q
from common.age import can_view_sensitive
from content.models import Submission

from .visibility import provenance_rows


def viewable_submissions(user):
    queryset = Submission.objects.select_related("classroom")
    if user.is_staff:
        return queryset
    if can_view_sensitive(user):
        return queryset.filter(visible_submissions_q(user)).distinct()
    supervised = supervised_q(user, prefix="classroom__") & Q(is_sensitive=False)
    return queryset.filter(Q(user=user) | supervised).distinct()


class ProvenanceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, submission_id):
        submission = get_object_or_404(viewable_submissions(request.user), id=submission_id)
        return Response(provenance_rows(submission, request.user))
