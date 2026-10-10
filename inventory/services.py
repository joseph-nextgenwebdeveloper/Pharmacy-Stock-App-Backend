"""The ONE place stock changes.

Every route that moves stock (the stock-movements API, creating a batch,
receiving a delivery, dispensing a sale) goes through `record_movement`, so
the rules can't drift apart:

* quantity must be above 0
* stock can never go negative
* expired medicine can't be *dispensed* (it can still be written off)
* every change writes a ledger row, linked to the signed-in user
* every change is logged to the activity feed
* low / out-of-stock alerts are re-evaluated straight away
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.audit import log_activity
from accounts.models import ActivityLog

from .models import Batch, StockMovement


def default_reason(movement_type):
    return (
        StockMovement.REASON_RECEIVED
        if movement_type == "IN"
        else StockMovement.REASON_DISPENSED
    )


@transaction.atomic
def record_movement(
    *,
    user,
    batch,
    quantity,
    movement_type,
    reason="",
    note="",
    reference="",
    new_batch=False,
):
    movement_type = (movement_type or "").upper()
    if movement_type not in ("IN", "OUT"):
        raise ValidationError({"movement_type": "Must be IN or OUT."})

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValidationError({"quantity": "Enter a whole number."})
    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be above 0."})

    reason = reason or default_reason(movement_type)
    allowed = (
        StockMovement.IN_REASONS if movement_type == "IN" else StockMovement.OUT_REASONS
    )
    if reason not in allowed:
        raise ValidationError(
            {"reason": f"'{reason}' is not a valid reason for stock {movement_type.lower()}."}
        )

    # Lock the row so two people can't both pass the "enough stock" check.
    locked = Batch.objects.select_for_update().select_related("medicine").get(pk=batch.pk)
    medicine = locked.medicine
    before = locked.quantity

    if movement_type == "OUT":
        if (
            reason == StockMovement.REASON_DISPENSED
            and locked.expiry_date < timezone.localdate()
        ):
            raise ValidationError(
                {
                    "batch": (
                        f"Batch {locked.batch_number} expired on {locked.expiry_date:%d %b %Y}"
                        " and can't be dispensed. Write it off as 'Expired' instead."
                    )
                }
            )
        if quantity > before:
            raise ValidationError(
                {"quantity": f"Not enough stock in this batch (only {before} left)."}
            )
        after = before - quantity
    else:
        after = before + quantity

    locked.quantity = after
    locked.save(update_fields=["quantity"])

    movement = StockMovement.objects.create(
        medicine=medicine,
        batch=locked,
        quantity=quantity,
        movement_type=movement_type,
        reason=reason,
        note=note or "",
        reference=reference or "",
        performed_by=user,
        quantity_before=before,
        quantity_after=after,
    )

    sign = 1 if movement_type == "IN" else -1
    label = dict(StockMovement.REASON_CHOICES).get(reason, reason)
    verb = "Received" if movement_type == "IN" else "Removed"
    if reason == StockMovement.REASON_DISPENSED:
        verb = "Dispensed"
    where = (
        f"into new batch {locked.batch_number}"
        if new_batch
        else f"(batch {locked.batch_number})"
    )
    log_activity(
        user,
        ActivityLog.STOCK_IN if movement_type == "IN" else ActivityLog.STOCK_OUT,
        f"{verb} {quantity} × {medicine.name} {where}",
        target=medicine,
        target_label=medicine.name,
        quantity=sign * quantity,
        changes={
            "batch": locked.batch_number,
            "reason": label,
            "reference": reference or "",
            "note": note or "",
            "balance_before": before,
            "balance_after": after,
            **({"expiry_date": str(locked.expiry_date)} if new_batch else {}),
        },
    )

    # Alerts are a side effect: never let them undo or block the stock change.
    try:
        from notifications.services import sync_medicine_alerts

        with transaction.atomic():
            sync_medicine_alerts(medicine)
    except Exception:  # pragma: no cover
        pass

    return movement


@transaction.atomic
def create_batch_with_stock(
    *,
    user,
    medicine,
    batch_number,
    expiry_date,
    quantity,
    buying_price,
    selling_price=0,
    manufacture_date=None,
    supplier=None,
    reference="",
    note="",
):
    """Create a batch AND book its opening stock through the ledger, so the
    movement history always accounts for every unit in the batch."""
    batch = Batch.objects.create(
        medicine=medicine,
        batch_number=batch_number,
        manufacture_date=manufacture_date,
        expiry_date=expiry_date,
        quantity=0,
        original_quantity=quantity,
        buying_price=buying_price,
        selling_price=selling_price,
        supplier=supplier,
    )

    if quantity > 0:
        # The opening stock is logged as the STOCK_IN row ("Received 100 x
        # Paracetamol into new batch PAR-001") rather than two rows.
        record_movement(
            user=user,
            batch=batch,
            quantity=quantity,
            movement_type="IN",
            reason=StockMovement.REASON_RECEIVED,
            reference=reference,
            note=note or f"Opening stock for batch {batch_number}",
            new_batch=True,
        )
        batch.refresh_from_db()
    else:
        log_activity(
            user,
            ActivityLog.BATCH_CREATED,
            f"Created batch {batch_number} of {medicine.name}",
            target=batch,
            target_label=f"{medicine.name} · {batch_number}",
            changes={
                "expiry_date": str(expiry_date),
                "supplier": supplier.name if supplier else "",
            },
        )

    return batch
