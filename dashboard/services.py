from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import ActivityLog
from inventory.models import Batch, Medicine, StockMovement
from notifications.models import Notification
from sales.models import Sale


def get_dashboard_data(user):
    today = timezone.localdate()

    total_medicines = Medicine.objects.count()

    total_stock = Batch.objects.aggregate(total=Sum("quantity"))["total"] or 0

    low_stock = 0
    out_of_stock = 0

    for medicine in Medicine.objects.all():
        stock = medicine.batches.aggregate(total=Sum("quantity"))["total"] or 0

        if stock == 0:
            out_of_stock += 1
        elif stock <= medicine.reorder_level:
            low_stock += 1

    healthy_stock = total_medicines - low_stock - out_of_stock

    today_received = (
        StockMovement.objects.filter(movement_type="IN", date=today).aggregate(
            total=Sum("quantity")
        )["total"]
        or 0
    )

    today_dispensed = (
        StockMovement.objects.filter(movement_type="OUT", date=today).aggregate(
            total=Sum("quantity")
        )["total"]
        or 0
    )

    today_sales = Sale.objects.filter(created_at__date=today).count()

    unread_notifications = Notification.objects.filter(
        receiver=user,
        is_read=False,
    ).count()

    live_batches = Batch.objects.filter(quantity__gt=0)
    expired_batches = live_batches.filter(expiry_date__lt=today).count()
    expiring_batches = live_batches.filter(
        expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)
    ).count()

    # Last 7 days (oldest first) of units in / out — the "weekly movements".
    week_start = today - timedelta(days=6)
    rows = (
        StockMovement.objects.filter(date__gte=week_start, date__lte=today)
        .values("date")
        .annotate(
            units_in=Sum("quantity", filter=Q(movement_type="IN")),
            units_out=Sum("quantity", filter=Q(movement_type="OUT")),
        )
    )
    by_day = {r["date"]: r for r in rows}
    weekly_movements = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        row = by_day.get(day)
        weekly_movements.append(
            {
                "date": day.isoformat(),
                "units_in": (row["units_in"] or 0) if row else 0,
                "units_out": (row["units_out"] or 0) if row else 0,
            }
        )

    my_updates_today = (
        ActivityLog.objects.filter(user=user, created_at__date=today)
        .exclude(action__in=ActivityLog.NOT_UPDATES)
        .count()
    )

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
        "expired_batches": expired_batches,
        "expiring_batches": expiring_batches,
        "weekly_movements": weekly_movements,
        "my_updates_today": my_updates_today,
    }
