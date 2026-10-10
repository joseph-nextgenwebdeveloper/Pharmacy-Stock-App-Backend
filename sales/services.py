from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.audit import log_activity
from accounts.models import ActivityLog
from inventory.models import StockMovement
from inventory.services import record_movement

from .models import Sale, SaleItem


@transaction.atomic
def create_sale(*, user, receipt_number, payment_method, items):
    """
    Records a dispensing/sale: reduces batch stock through the stock ledger
    (one OUT movement per line, reason "Dispensed", linked to the user).
    """

    if not items:
        raise ValidationError("A sale must contain at least one item.")

    # Prevent duplicate receipt numbers
    if Sale.objects.filter(receipt_number=receipt_number).exists():
        raise ValidationError("A sale with this receipt number already exists.")

    validated_items = []
    total_amount = 0

    for item in items:
        medicine = item["medicine"]
        batch = item["batch"]
        quantity = item["quantity"]
        unit_price = item["unit_price"]

        # Make sure the batch belongs to the medicine
        if batch.medicine_id != medicine.id:
            raise ValidationError(
                f"Batch {batch.id} does not belong to medicine {medicine.name}."
            )

        # Prevent dispensing expired medicine
        if batch.expiry_date < timezone.localdate():
            raise ValidationError(
                f"Batch {batch.batch_number} of {medicine.name} has expired."
            )

        # Prevent negative stock
        if batch.quantity < quantity:
            raise ValidationError(
                f"Insufficient stock for {medicine.name}. "
                f"Available: {batch.quantity}, requested: {quantity}."
            )

        subtotal = quantity * unit_price
        total_amount += subtotal

        validated_items.append(
            {
                "medicine": medicine,
                "batch": batch,
                "quantity": quantity,
                "unit_price": unit_price,
                "subtotal": subtotal,
            }
        )

    sale = Sale.objects.create(
        receipt_number=receipt_number,
        sold_by=user,
        payment_method=payment_method,
        total_amount=total_amount,
    )

    for item in validated_items:
        # record_movement locks the batch, re-checks stock and expiry, writes
        # the ledger row + activity entry and refreshes the stock alerts.
        movement = record_movement(
            user=user,
            batch=item["batch"],
            quantity=item["quantity"],
            movement_type="OUT",
            reason=StockMovement.REASON_DISPENSED,
            reference=receipt_number,
        )

        SaleItem.objects.create(
            sale=sale,
            medicine=item["medicine"],
            batch=movement.batch,
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            subtotal=item["subtotal"],
        )

    log_activity(
        user,
        ActivityLog.SALE_CREATED,
        f"Recorded dispensing {receipt_number} ({len(validated_items)} item(s))",
        target=sale,
        target_label=receipt_number,
    )

    return sale
