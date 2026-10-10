from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.services import sync_all_alerts

from .serializers import DashboardSerializer
from .services import get_dashboard_data


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Keeps alert repeats flowing whenever someone opens the app (throttled).
        try:
            sync_all_alerts()
        except Exception:
            pass

        data = get_dashboard_data(request.user)
        serializer = DashboardSerializer(data)

        return Response(serializer.data)
