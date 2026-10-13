from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ProvenanceResult
from .serializers import ProvenanceResultSerializer
from .visibility import results_for_viewer, sensitive_match_ids


class ProvenanceListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProvenanceResultSerializer
    pagination_class = None

    def get_queryset(self):
        submission_id = self.kwargs["submission_id"]
        return ProvenanceResult.objects.filter(
            submission_id=submission_id,
            submission__user=self.request.user,
        )

    def list(self, request, *args, **kwargs):
        results = list(self.get_queryset())
        sensitive_ids = sensitive_match_ids(results)
        results = results_for_viewer(results, request.user, sensitive_ids)
        serializer = self.get_serializer(results, many=True, context={
            **self.get_serializer_context(),
            "sensitive_submission_ids": sensitive_ids,
        })
        return Response(serializer.data)
