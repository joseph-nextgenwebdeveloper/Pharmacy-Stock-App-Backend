from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from notifications.services import create_low_stock_notification,create_out_of_stock_notification
from inventory.models import Batch, StockMovement
from .models import Sale, SaleItem


@transaction.atomic
def create_sale(*, user, receipt_number, payment_method, items):
    """
    Creates a sale, reduces batch stock,
    and records stock movements.
    """

    if not items:
        raise ValidationError(
            "A sale must contain at least one item."
        )

    # Prevent duplicate receipt numbers
    if Sale.objects.filter(
        receipt_number=receipt_number
    ).exists():
        raise ValidationError(
            "A sale with this receipt number already exists."
        )

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
                f"Batch {batch.id} does not belong to "
                f"medicine {medicine.name}."
            )

        # Prevent dispensing expired medicine
        if batch.expiry_date < timezone.localdate():
            raise ValidationError(
                f"Batch {batch.batch_number} of "
                f"{medicine.name} has expired."
            )

        # Prevent negative stock
        if batch.quantity < quantity:
            raise ValidationError(
                f"Insufficient stock for {medicine.name}. "
                f"Available: {batch.quantity}, "
                f"requested: {quantity}."
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

    # Create the sale
    sale = Sale.objects.create(
        receipt_number=receipt_number,
        sold_by=user,
        payment_method=payment_method,
        total_amount=total_amount,
    )

    # Reduce stock and create movement records
    for item in validated_items:

        batch = Batch.objects.select_for_update().get(
            pk=item["batch"].pk
        )

        # Double-check stock after locking the batch
        if batch.quantity < item["quantity"]:
            raise ValidationError(
                f"Insufficient stock for "
                f"{item['medicine'].name}."
            )

        batch.quantity -= item["quantity"]

        batch.save(
            update_fields=["quantity"]
        )
        
        
        medicine = item["medicine"]

        total_stock = (
                medicine.batches.aggregate(total=Sum("quantity"))["total"] or 0
            )

        if total_stock == 0:
            create_out_of_stock_notification(user, medicine)

        elif total_stock <= medicine.reorder_level:
            create_low_stock_notification(
                user, medicine,
                total_stock,
                medicine.reorder_level,
            )

        # Create sale item
        SaleItem.objects.create(
            sale=sale,
            medicine=item["medicine"],
            batch=batch,
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            subtotal=item["subtotal"],
        )

        # Record inventory movement
        StockMovement.objects.create(
            medicine=item["medicine"],
            batch=batch,
            quantity=item["quantity"],
            movement_type="OUT",
            performed_by=user,
        )

    return sale