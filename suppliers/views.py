from rest_framework import filters, generics
from rest_framework.permissions import IsAuthenticated

from accounts.audit import diff, log_activity, snapshot
from accounts.models import ActivityLog

from .models import Supplier
from .serializers import SupplierSerializer

SUPPLIER_FIELDS = [
    "name",
    "company_name",
    "contact_person",
    "email",
    "phone_number",
    "address",
    "is_active",
]


class SupplierListCreateView(generics.ListCreateAPIView):
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "name",
        "company_name",
        "contact_person",
        "email",
        "phone_number",
    ]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        return Supplier.objects.filter(is_active=True)

    def perform_create(self, serializer):
        supplier = serializer.save()
        log_activity(
            self.request.user,
            ActivityLog.SUPPLIER_CREATED,
            f"Added supplier {supplier.name}",
            target=supplier,
        )


class SupplierDetailView(generics.RetrieveUpdateAPIView):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        before = snapshot(serializer.instance, SUPPLIER_FIELDS)
        supplier = serializer.save()
        changes = diff(before, snapshot(supplier, SUPPLIER_FIELDS))
        if changes:
            log_activity(
                self.request.user,
                ActivityLog.SUPPLIER_UPDATED,
                f"Edited supplier {supplier.name}",
                target=supplier,
                changes=changes,
            )
