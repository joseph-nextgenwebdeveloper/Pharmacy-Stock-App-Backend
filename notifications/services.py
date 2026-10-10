"""Stock / expiry / delivery alerts.

How an alert behaves
--------------------
* The first time a problem appears (a medicine hits 0, a batch expires...)
  every active staff member gets a notification.
* While the problem is NOT fixed the alert stays open and is repeated: an
  out-of-stock alert every 2 hours, low-stock / expiry alerts once a day. A
  repeat re-opens the SAME notification (unread, newest first, reminder
  counter +1) instead of piling up duplicates.
* As soon as the problem is fixed (stock added, batch used up) the open
  alert is resolved and stops repeating.

`sync_medicine_alerts` runs right after every stock change. `sync_all_alerts`
re-checks everything (and sends the due repeats); it runs, throttled, when
the app asks for its notifications or dashboard, and from the
`send_stock_reminders` management command (run it from a Render Cron Job
every 15-30 minutes for repeats while nobody has the app open).
"""
import time
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import F, Sum
from django.utils import timezone

from .models import Notification, NotificationType

OUT_OF_STOCK_REPEAT = timedelta(hours=2)
LOW_STOCK_REPEAT = timedelta(hours=24)
EXPIRY_REPEAT = timedelta(hours=24)

_SYNC_THROTTLE_SECONDS = 60
_last_sync = 0.0


def staff_receivers():
    return get_user_model().objects.filter(is_active=True)


def _open(receiver, notification_type, medicine=None, batch=None):
    return Notification.objects.filter(
        receiver=receiver,
        notification_type=notification_type,
        medicine=medicine,
        batch=batch,
        is_resolved=False,
    )


def _notify(
    receiver,
    notification_type,
    title,
    message,
    *,
    medicine=None,
    batch=None,
    repeat_every=None,
    now=None,
):
    """Create the alert, or repeat it if it is open and due. Returns the row."""
    now = now or timezone.now()
    existing = _open(receiver, notification_type, medicine, batch).order_by("-id").first()

    if existing is None:
        return Notification.objects.create(
            receiver=receiver,
            medicine=medicine,
            batch=batch,
            notification_type=notification_type,
            title=title,
            message=message,
        )

    changed = {}
    if existing.message != message:
        changed["message"] = message

    if repeat_every is not None and now - existing.created_at >= repeat_every:
        # Same alert, shown again: newest, unread, reminder counter up.
        Notification.objects.filter(pk=existing.pk).update(
            created_at=now,
            is_read=False,
            reminder_count=F("reminder_count") + 1,
            **changed,
        )
    elif changed:
        Notification.objects.filter(pk=existing.pk).update(**changed)

    existing.refresh_from_db()
    return existing


def _resolve(notification_type, *, medicine=None, batch=None, now=None):
    now = now or timezone.now()
    qs = Notification.objects.filter(
        notification_type=notification_type, is_resolved=False
    )
    if medicine is not None:
        qs = qs.filter(medicine=medicine)
    if batch is not None:
        qs = qs.filter(batch=batch)
    return qs.update(is_resolved=True, resolved_at=now, is_read=True)


# ----------------------------------------------------------------- stock


def medicine_stock(medicine):
    return medicine.batches.aggregate(total=Sum("quantity"))["total"] or 0


def sync_medicine_alerts(medicine, *, now=None):
    """Re-evaluate ONE medicine against its stock and reorder level."""
    now = now or timezone.now()
    stock = medicine_stock(medicine)
    receivers = list(staff_receivers())

    if stock <= 0:
        _resolve(NotificationType.LOW_STOCK, medicine=medicine, now=now)
        for user in receivers:
            _notify(
                user,
                NotificationType.OUT_OF_STOCK,
                "Out of Stock",
                f"{medicine.name} is out of stock. Receive new stock to clear this alert.",
                medicine=medicine,
                repeat_every=OUT_OF_STOCK_REPEAT,
                now=now,
            )
    elif stock <= medicine.reorder_level:
        _resolve(NotificationType.OUT_OF_STOCK, medicine=medicine, now=now)
        for user in receivers:
            _notify(
                user,
                NotificationType.LOW_STOCK,
                "Low Stock Alert",
                f"{medicine.name} is running low. Current stock: {stock}. "
                f"Reorder level: {medicine.reorder_level}.",
                medicine=medicine,
                repeat_every=LOW_STOCK_REPEAT,
                now=now,
            )
    else:
        _resolve(NotificationType.OUT_OF_STOCK, medicine=medicine, now=now)
        _resolve(NotificationType.LOW_STOCK, medicine=medicine, now=now)


def sync_expiry_alerts(*, now=None):
    from inventory.models import Batch

    now = now or timezone.now()
    today = timezone.localdate()
    receivers = list(staff_receivers())

    live = Batch.objects.filter(quantity__gt=0).select_related("medicine")
    expired_ids, expiring_ids = set(), set()

    for batch in live:
        medicine = batch.medicine
        if batch.expiry_date < today:
            expired_ids.add(batch.pk)
            for user in receivers:
                _notify(
                    user,
                    NotificationType.MEDICINE_EXPIRED,
                    "Medicine Expired",
                    f"{medicine.name}, batch {batch.batch_number}, expired on "
                    f"{batch.expiry_date:%d %b %Y} with {batch.quantity} unit(s) "
                    "still in stock. It cannot be dispensed.",
                    medicine=medicine,
                    batch=batch,
                    repeat_every=EXPIRY_REPEAT,
                    now=now,
                )
        elif batch.expiry_date <= today + timedelta(days=medicine.expiry_alert_days):
            expiring_ids.add(batch.pk)
            for user in receivers:
                _notify(
                    user,
                    NotificationType.MEDICINE_EXPIRING,
                    "Medicine Expiring Soon",
                    f"{medicine.name}, batch {batch.batch_number}, expires on "
                    f"{batch.expiry_date:%d %b %Y} ({batch.quantity} unit(s) left).",
                    medicine=medicine,
                    batch=batch,
                    repeat_every=EXPIRY_REPEAT,
                    now=now,
                )

    # Close alerts whose batch is used up / no longer in that state.
    Notification.objects.filter(
        notification_type=NotificationType.MEDICINE_EXPIRED, is_resolved=False
    ).exclude(batch_id__in=expired_ids).update(
        is_resolved=True, resolved_at=now, is_read=True
    )
    Notification.objects.filter(
        notification_type=NotificationType.MEDICINE_EXPIRING, is_resolved=False
    ).exclude(batch_id__in=expiring_ids).update(
        is_resolved=True, resolved_at=now, is_read=True
    )


def sync_all_alerts(*, force=False, now=None):
    """Re-check every medicine and batch and send any repeat that is due."""
    global _last_sync
    clock = time.monotonic()
    if not force and clock - _last_sync < _SYNC_THROTTLE_SECONDS:
        return False
    _last_sync = clock

    from inventory.models import Medicine

    for medicine in Medicine.objects.all():
        sync_medicine_alerts(medicine, now=now)
    sync_expiry_alerts(now=now)
    return True


# ------------------------------------------------- delivery notifications


def create_notification(receiver, notification_type, message, title=None, medicine=None):
    return _notify(
        receiver, notification_type, title, message, medicine=medicine
    )


def create_low_stock_notification(receiver, medicine, quantity, reorder_level):
    return _notify(
        receiver,
        NotificationType.LOW_STOCK,
        "Low Stock Alert",
        f"{medicine.name} is running low. Current stock: {quantity}. "
        f"Reorder level: {reorder_level}.",
        medicine=medicine,
        repeat_every=LOW_STOCK_REPEAT,
    )


def create_out_of_stock_notification(receiver, medicine):
    return _notify(
        receiver,
        NotificationType.OUT_OF_STOCK,
        "Out of Stock",
        f"{medicine.name} is out of stock. Receive new stock to clear this alert.",
        medicine=medicine,
        repeat_every=OUT_OF_STOCK_REPEAT,
    )


def notify_staff_purchase_received(supplier, *, actor=None, units=None):
    """Tell everyone a delivery arrived (one-off; resolved immediately)."""
    who = actor.display_name if actor is not None else "Someone"
    extra = f" ({units} units)" if units else ""
    for user in staff_receivers():
        Notification.objects.create(
            receiver=user,
            notification_type=NotificationType.PURCHASE_RECEIVED,
            title="Delivery Received",
            message=f"{who} received a stock delivery from {supplier.name}{extra}.",
            is_resolved=True,
        )


def create_purchase_received_notification(receiver, supplier):
    return Notification.objects.create(
        receiver=receiver,
        notification_type=NotificationType.PURCHASE_RECEIVED,
        title="Purchase Received",
        message=f"Stock delivery from {supplier.name} has been received.",
        is_resolved=True,
    )


def create_purchase_cancelled_notification(receiver, supplier):
    return Notification.objects.create(
        receiver=receiver,
        notification_type=NotificationType.PURCHASE_CANCELLED,
        title="Purchase Cancelled",
        message=f"Stock delivery from {supplier.name} has been cancelled.",
        is_resolved=True,
    )
