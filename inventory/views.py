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


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer


    @transaction.atomic
    def perform_create(self, serializer):
        medicine = serializer.validated_data["medicine"]
        batch = serializer.validated_data["batch"]
        quantity = serializer.validated_data["quantity"]
        movement_type = serializer.validated_data["movement_type"]

        if batch.medicine != medicine:
            raise ValidationError(
                "The selected batch does not belong to the selected medicine."
            )

        if movement_type == "IN":
            batch.quantity += quantity

        elif movement_type == "OUT":
            if batch.expiry_date < date.today():
                raise ValidationError(
                "This batch has expired and cannot be dispensed."
            )
            if batch.quantity < quantity:
                raise ValidationError(
                    "Insufficient stock in this batch."
                )

            batch.quantity -= quantity

        batch.save()

        serializer.save(performed_by=self.request.user)