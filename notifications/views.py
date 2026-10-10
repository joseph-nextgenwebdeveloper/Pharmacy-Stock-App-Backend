from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from pharmacy_config.pagination import LargeResultsSetPagination

from .models import Notification
from .serializers import NotificationSerializer
from .services import sync_all_alerts


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        return Notification.objects.filter(receiver=self.request.user).order_by(
            "-created_at", "-id"
        )

    def list(self, request, *args, **kwargs):
        # Opening the feed re-checks stock/expiry and sends any repeat that is
        # due (throttled), so alerts keep coming even without a scheduler.
        try:
            sync_all_alerts()
        except Exception:
            pass
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])

        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"updated": updated})
