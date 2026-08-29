from django.db.models import Sum
from django.utils import timezone

from inventory.models import Batch, Medicine, StockMovement
from sales.models import SaleItem


def get_inventory_report():
    report = []

    for medicine in Medicine.objects.all():
        quantity = (
            medicine.batches.aggregate(total=Sum("quantity"))["total"] or 0
        )

        if quantity == 0:
            status = "OUT_OF_STOCK"
        elif quantity <= medicine.reorder_level:
            status = "LOW_STOCK"
        else:
            status = "HEALTHY"

        report.append({
            "medicine": medicine.name,
            "sku": medicine.sku,
            "quantity": quantity,
            "reorder_level": medicine.reorder_level,
            "status": status,
        })

    return report


def get_monthly_movement_report(year, month):
    movements = StockMovement.objects.filter(
        movement_date__year=year,
        movement_date__month=month,
    )

    received = (
        movements.filter(movement_type="IN")
        .aggregate(total=Sum("quantity"))["total"] or 0
    )

    dispensed = (
        movements.filter(movement_type="OUT")
        .aggregate(total=Sum("quantity"))["total"] or 0
    )

    return {
        "year": year,
        "month": month,
        "stock_received": received,
        "stock_dispensed": dispensed,
    }


def get_expired_medicines():
    today = timezone.localdate()

    batches = Batch.objects.filter(
        expiry_date__lt=today,
        quantity__gt=0,
    ).select_related("medicine")

    return [
        {
            "medicine": batch.medicine.name,
            "sku": batch.medicine.sku,
            "batch_number": batch.batch_number,
            "expiry_date": batch.expiry_date,
            "quantity": batch.quantity,
        }
        for batch in batches
    ]


def get_stock_valuation():
    report = []

    for medicine in Medicine.objects.all():
        batches = medicine.batches.all()

        quantity = (
            batches.aggregate(total=Sum("quantity"))["total"] or 0
        )

        value = sum(
            batch.quantity * batch.buying_price
            for batch in batches
        )

        report.append({
            "medicine": medicine.name,
            "sku": medicine.sku,
            "quantity": quantity,
            "stock_value": value,
        })

    return report


def get_fast_moving_medicines():
    movements = (
        SaleItem.objects
        .values("medicine", "medicine__name", "medicine__sku")
        .annotate(total_dispensed=Sum("quantity"))
        .order_by("-total_dispensed")
    )

    return [
        {
            "medicine": item["medicine__name"],
            "sku": item["medicine__sku"],
            "quantity_dispensed": item["total_dispensed"],
        }
        for item in movements
    ]


def get_slow_moving_medicines():
    movements = (
        SaleItem.objects
        .values("medicine", "medicine__name", "medicine__sku")
        .annotate(total_dispensed=Sum("quantity"))
        .order_by("total_dispensed")
    )

    return [
        {
            "medicine": item["medicine__name"],
            "sku": item["medicine__sku"],
            "quantity_dispensed": item["total_dispensed"],
        }
        for item in movements
    ]