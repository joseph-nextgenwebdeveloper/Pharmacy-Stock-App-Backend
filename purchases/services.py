from django.db import transaction

from accounts.audit import log_activity
from accounts.models import ActivityLog
from inventory.services import create_batch_with_stock
from notifications.services import notify_staff_purchase_received

from .models import GoodsReceived, GoodsReceivedItem


@transaction.atomic
def create_goods_received(*, user, supplier, items, invoice_number="", notes=""):
    """One supplier delivery. Every line becomes its OWN batch (one lot of one
    medicine), booked through the stock ledger as stock-in under reference
    GRN-<id>, by the signed-in user."""
    if not items:
        raise ValueError("A delivery must contain at least one item.")

    goods_received = GoodsReceived.objects.create(
        supplier=supplier,
        invoice_number=invoice_number,
        received_by=user,
        notes=notes,
    )
    reference = f"GRN-{goods_received.id}"
    if invoice_number:
        reference = f"{reference} · INV {invoice_number}"

    total_units = 0
    for item in items:
        received_item = GoodsReceivedItem.objects.create(
            goods_received=goods_received,
            **item,
        )

        create_batch_with_stock(
            user=user,
            medicine=received_item.medicine,
            batch_number=received_item.batch_number,
            manufacture_date=received_item.manufacture_date,
            expiry_date=received_item.expiry_date,
            quantity=received_item.quantity,
            buying_price=received_item.buying_price,
            selling_price=received_item.selling_price,
            supplier=supplier,
            reference=reference,
            note=notes or "",
        )
        total_units += received_item.quantity

    log_activity(
        user,
        ActivityLog.GOODS_RECEIVED,
        f"Received delivery GRN-{goods_received.id} from {supplier.name} "
        f"({len(items)} batch(es), {total_units} units)",
        target=goods_received,
        target_label=f"GRN-{goods_received.id}",
    )
    notify_staff_purchase_received(supplier, actor=user, units=total_units)

    return goods_received
