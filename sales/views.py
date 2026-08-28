from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Sale
from .serializers import SaleSerializer


class SaleViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        sales = Sale.objects.all().order_by("-created_at")
        serializer = SaleSerializer(
            sales,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        try:
            sale = Sale.objects.get(pk=pk)
        except Sale.DoesNotExist:
            return Response(
                {"detail": "Sale not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SaleSerializer(
            sale,
            context={"request": request},
        )

        return Response(serializer.data)

    def create(self, request):
        serializer = SaleSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        sale = serializer.save()

        response_serializer = SaleSerializer(
            sale,
            context={"request": request},
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )