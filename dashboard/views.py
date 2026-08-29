from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import DashboardSerializer
from .services import get_dashboard_data


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_dashboard_data(request.user)
        serializer = DashboardSerializer(data)

        return Response(serializer.data)