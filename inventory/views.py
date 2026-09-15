from datetime import date
from rest_framework.exceptions import ValidationError
from rest_framework import viewsets
from inventory.models import Category, Medicine, Batch, StockMovement
from inventory.serializers import BatchSerializer, CategorySerializer, MedicineSerializer, StockMovementSerializer 
from django.db import transaction
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = [
        "name",
        "generic_name",
        "sku",
    ]
    filterset_fields = [
    "category",
    ]
    ordering_fields = [
    "name",
    "generic_name",
    "sku",
    ]
    ordering = ["name"]


class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.all().order_by("-movement_date")
    serializer_class = StockMovementSerializer