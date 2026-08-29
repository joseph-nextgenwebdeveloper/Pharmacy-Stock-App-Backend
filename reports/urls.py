from django.urls import path

from .views import (
    ExpiredMedicineReportView,
    FastMovingMedicineView,
    InventoryReportView,
    MonthlyMovementReportView,
    SlowMovingMedicineView,
    StockValuationReportView,
)


urlpatterns = [
    path("inventory/", InventoryReportView.as_view(), name="inventory-report"),
    path("monthly-movements/", MonthlyMovementReportView.as_view(), name="monthly-movement-report"),
    path("expired/", ExpiredMedicineReportView.as_view(), name="expired-report"),
    path("valuation/", StockValuationReportView.as_view(), name="stock-valuation-report"),
    path("fast-moving/", FastMovingMedicineView.as_view(), name="fast-moving-report"),
    path("slow-moving/", SlowMovingMedicineView.as_view(), name="slow-moving-report"),
]