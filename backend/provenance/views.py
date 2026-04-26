from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from .models import ProvenanceResult
from .serializers import ProvenanceResultSerializer


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
