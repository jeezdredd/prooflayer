from rest_framework import permissions, serializers, viewsets

from api.models import RoadmapItem


class RoadmapItemSerializer(serializers.ModelSerializer):
    body = serializers.CharField(allow_blank=True, required=False, max_length=600)

    class Meta:
        model = RoadmapItem
        fields = ["id", "title", "body", "status", "eta", "position", "is_published", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class StaffWriteOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class RoadmapItemViewSet(viewsets.ModelViewSet):
    serializer_class = RoadmapItemSerializer
    permission_classes = [StaffWriteOrReadOnly]
    pagination_class = None
    lookup_field = "id"

    def get_queryset(self):
        items = RoadmapItem.objects.all()
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return items
        return items.filter(is_published=True)
