from datetime import timedelta

from django.db.models import ProtectedError, Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.audit import diff, log_activity, snapshot
from accounts.models import ActivityLog
from pharmacy_config.pagination import LargeResultsSetPagination

from .models import Batch, Category, Medicine, StockMovement
from .serializers import (
    BatchSerializer,
    CategorySerializer,
    MedicineSerializer,
    StockMovementSerializer,
)
from .services import create_batch_with_stock, record_movement

MEDICINE_FIELDS = [
    "name",
    "generic_name",
    "description",
    "category",
    "sku",
    "barcode",
    "units",
    "reorder_level",
    "expiry_alert_days",
    "image",
]
BATCH_FIELDS = [
    "batch_number",
    "manufacture_date",
    "expiry_date",
    "buying_price",
    "selling_price",
    "supplier",
]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        category = serializer.save()
        log_activity(
            self.request.user,
            ActivityLog.CATEGORY_CREATED,
            f"Added category {category.name}",
            target=category,
        )


class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeResultsSetPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = ["name", "generic_name", "sku", "barcode"]
    filterset_fields = ["category"]
    ordering_fields = ["name", "generic_name", "sku"]
    ordering = ["name"]

    def perform_create(self, serializer):
        medicine = serializer.save()
        log_activity(
            self.request.user,
            ActivityLog.MEDICINE_CREATED,
            f"Added medicine {medicine.name}",
            target=medicine,
            changes={"sku": medicine.sku, "barcode": medicine.barcode or ""},
        )

    def perform_update(self, serializer):
        before = snapshot(serializer.instance, MEDICINE_FIELDS)
        medicine = serializer.save()
        changes = diff(before, snapshot(medicine, MEDICINE_FIELDS))
        if changes:
            log_activity(
                self.request.user,
                ActivityLog.MEDICINE_UPDATED,
                f"Edited medicine {medicine.name}",
                target=medicine,
                changes=changes,
            )

    def destroy(self, request, *args, **kwargs):
        medicine = self.get_object()
        name, pk = medicine.name, medicine.pk
        try:
            medicine.delete()
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        f"{name} has stock history and can't be deleted. "
                        "Its movements must stay on record."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_activity(
            request.user,
            ActivityLog.MEDICINE_DELETED,
            f"Deleted medicine {name}",
            target_type="Medicine",
            target_id=pk,
            target_label=name,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BatchViewSet(viewsets.ModelViewSet):
    """Real stock batches: one received lot of ONE medicine.

    Creating a batch books its opening quantity through the stock ledger
    (an IN movement by the signed-in user). Quantity can't be edited
    afterwards — it only changes through stock movements."""

    queryset = Batch.objects.select_related("medicine", "supplier")
    serializer_class = BatchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeResultsSetPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = [
        "batch_number",
        "medicine__name",
        "medicine__sku",
        "supplier__name",
    ]
    filterset_fields = ["medicine", "supplier"]
    ordering_fields = ["expiry_date", "quantity", "received_date", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        today = timezone.localdate()

        status_filter = (params.get("status") or "").upper()
        if status_filter == Batch.STATUS_DEPLETED:
            qs = qs.filter(quantity__lte=0)
        elif status_filter == Batch.STATUS_EXPIRED:
            qs = qs.filter(quantity__gt=0, expiry_date__lt=today)
        elif status_filter == Batch.STATUS_ACTIVE:
            qs = qs.filter(quantity__gt=0, expiry_date__gte=today)

        days = params.get("expiring_within")
        if days and days.isdigit():
            qs = qs.filter(
                quantity__gt=0,
                expiry_date__gte=today,
                expiry_date__lte=today + timedelta(days=int(days)),
            )
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        quantity = data.get("quantity", 0)
        batch = create_batch_with_stock(
            user=self.request.user,
            medicine=data["medicine"],
            batch_number=data["batch_number"],
            expiry_date=data["expiry_date"],
            quantity=quantity,
            buying_price=data["buying_price"],
            selling_price=data.get("selling_price", 0),
            manufacture_date=data.get("manufacture_date"),
            supplier=data.get("supplier"),
        )
        serializer.instance = batch

    def perform_update(self, serializer):
        before = snapshot(serializer.instance, BATCH_FIELDS)
        batch = serializer.save()
        changes = diff(before, snapshot(batch, BATCH_FIELDS))
        if changes:
            log_activity(
                self.request.user,
                ActivityLog.BATCH_UPDATED,
                f"Edited batch {batch.batch_number} of {batch.medicine.name}",
                target=batch,
                target_label=f"{batch.medicine.name} · {batch.batch_number}",
                changes=changes,
            )

    def destroy(self, request, *args, **kwargs):
        batch = self.get_object()
        label = f"{batch.medicine.name} · {batch.batch_number}"
        pk = batch.pk
        try:
            batch.delete()
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "This batch has stock movements and can't be deleted. "
                        "Use a stock adjustment to take the remaining units out."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_activity(
            request.user,
            ActivityLog.BATCH_DELETED,
            f"Deleted batch {label}",
            target_type="Batch",
            target_id=pk,
            target_label=label,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class StockMovementViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """The stock ledger. Read it, or add a movement — never edit or delete one.

    Filters: medicine, batch, movement_type, reason, performed_by (id or
    "me"), date, date_from, date_to, search."""

    queryset = StockMovement.objects.select_related(
        "medicine", "batch", "performed_by"
    ).order_by("-movement_date", "-id")
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeResultsSetPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["medicine", "batch", "movement_type", "reason"]
    search_fields = [
        "medicine__name",
        "batch__batch_number",
        "reference",
        "note",
        "performed_by__username",
        "performed_by__first_name",
        "performed_by__last_name",
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        who = params.get("performed_by")
        if who == "me":
            qs = qs.filter(performed_by=self.request.user)
        elif who and who.isdigit():
            qs = qs.filter(performed_by_id=who)

        if params.get("date"):
            qs = qs.filter(movement_date__date=params["date"])
        if params.get("date_from"):
            qs = qs.filter(movement_date__date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(movement_date__date__lte=params["date_to"])
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        movement = record_movement(
            user=self.request.user,
            batch=data["batch"],
            quantity=data["quantity"],
            movement_type=data["movement_type"],
            reason=data.get("reason", ""),
            note=data.get("note", ""),
            reference=data.get("reference", ""),
        )
        serializer.instance = movement
