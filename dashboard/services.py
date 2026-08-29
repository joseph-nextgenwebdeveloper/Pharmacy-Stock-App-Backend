from django.db.models import Sum
from django.utils import timezone

from inventory.models import Batch, Medicine, StockMovement
from notifications.models import Notification
from sales.models import Sale


def get_dashboard_data(user):
    today = timezone.localdate()

    total_medicines = Medicine.objects.count()

    total_stock = (
        Batch.objects.aggregate(total=Sum("quantity"))["total"] or 0
    )

    low_stock = 0
    out_of_stock = 0

    for medicine in Medicine.objects.all():
        stock = (
            medicine.batches.aggregate(total=Sum("quantity"))["total"] or 0
        )

        if stock == 0:
            out_of_stock += 1
        elif stock <= medicine.reorder_level:
            low_stock += 1

    healthy_stock = total_medicines - low_stock - out_of_stock

    today_received = StockMovement.objects.filter(
        movement_type="IN",
        date=today,
    ).aggregate(total=Sum("quantity"))["total"] or 0

    today_dispensed = StockMovement.objects.filter(
        movement_type="OUT",
        date=today,
    ).aggregate(total=Sum("quantity"))["total"] or 0

    today_sales = Sale.objects.filter(
        created_at__date=today
    ).count()

    unread_notifications = Notification.objects.filter(
        receiver=user,
        is_read=False,
    ).count()

    return {
        "total_medicines": total_medicines,
        "total_stock": total_stock,
        "healthy_stock": healthy_stock,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "today_received": today_received,
        "today_dispensed": today_dispensed,
        "today_sales": today_sales,
        "unread_notifications": unread_notifications,
    }