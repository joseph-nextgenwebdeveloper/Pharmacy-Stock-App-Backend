from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ExpiredMedicineReportSerializer,
    FastMovingMedicineSerializer,
    InventoryReportSerializer,
    MonthlyMovementReportSerializer,
    SlowMovingMedicineSerializer,
    StockValuationReportSerializer,
)
from .services import (
    get_expired_medicines,
    get_fast_moving_medicines,
    get_inventory_report,
    get_monthly_movement_report,
    get_slow_moving_medicines,
    get_stock_valuation,
)


class InventoryReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_inventory_report()
        serializer = InventoryReportSerializer(data, many=True)
        return Response(serializer.data)


class MonthlyMovementReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = int(request.query_params.get("year"))
        month = int(request.query_params.get("month"))

        data = get_monthly_movement_report(year, month)
        serializer = MonthlyMovementReportSerializer(data)

        return Response(serializer.data)


class ExpiredMedicineReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_expired_medicines()
        serializer = ExpiredMedicineReportSerializer(data, many=True)

        return Response(serializer.data)


class StockValuationReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_stock_valuation()
        serializer = StockValuationReportSerializer(data, many=True)

        return Response(serializer.data)


class FastMovingMedicineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_fast_moving_medicines()
        serializer = FastMovingMedicineSerializer(data, many=True)

        return Response(serializer.data)


class SlowMovingMedicineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_slow_moving_medicines()
        serializer = SlowMovingMedicineSerializer(data, many=True)

        return Response(serializer.data)