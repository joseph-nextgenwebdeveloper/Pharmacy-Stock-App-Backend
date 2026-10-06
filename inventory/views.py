from datetime import date
from rest_framework.exceptions import ValidationError
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from inventory.models import Category, Medicine, Batch, StockMovement
from inventory.serializers import BatchSerializer, CategorySerializer, MedicineSerializer, StockMovementSerializer 
from django.db import transaction
from django.db.models import Sum
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from notifications.services import (
    create_low_stock_notification,
    create_out_of_stock_notification,
)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]


class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all().order_by("-movement_date")
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        batch = serializer.validated_data["batch"]
        quantity = serializer.validated_data["quantity"]
        movement_type = serializer.validated_data["movement_type"]

        with transaction.atomic():
            # Lock the batch row so concurrent stock-out requests can't
            # both pass the "enough stock" check at once.
            locked_batch = Batch.objects.select_for_update().get(
                pk=batch.pk
            )

            if movement_type == "OUT":
                if quantity > locked_batch.quantity:
                    raise ValidationError(
                        {
                            "quantity": (
                                "Not enough stock in this batch "
                                f"(only {locked_batch.quantity} left)."
                            )
                        }
                    )
                locked_batch.quantity -= quantity
            else:
                locked_batch.quantity += quantity

            locked_batch.save(update_fields=["quantity"])

            serializer.save(
                performed_by=self.request.user,
                batch=locked_batch,
            )

        # Outside the transaction (and never allowed to break the actual
        # stock update if something here goes wrong, per the build notes'
        # "keep this decoupled" instruction): check whether this movement
        # just crossed the medicine into low/out-of-stock and notify.
        try:
            medicine = locked_batch.medicine
            total_quantity = (
                medicine.batches.aggregate(total=Sum("quantity"))["total"] or 0
            )

            if movement_type == "OUT":
                if total_quantity <= 0:
                    create_out_of_stock_notification(
                        receiver=self.request.user,
                        medicine=medicine,
                    )
                elif total_quantity <= medicine.reorder_level:
                    create_low_stock_notification(
                        receiver=self.request.user,
                        medicine=medicine,
                        quantity=total_quantity,
                        reorder_level=medicine.reorder_level,
                    )
        except Exception:
            pass