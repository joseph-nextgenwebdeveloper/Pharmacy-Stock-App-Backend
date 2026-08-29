from django.db import transaction

from inventory.models import Batch, StockMovement
from notifications.services import create_purchase_received_notification

from .models import GoodsReceived, GoodsReceivedItem


@transaction.atomic
def create_goods_received(*, user, supplier, invoice_number, notes, items):
    if not items:
        raise ValueError("A delivery must contain at least one item.")

    goods_received = GoodsReceived.objects.create(
        supplier=supplier,
        invoice_number=invoice_number,
        received_by=user,
        notes=notes,
    )

    for item in items:
        received_item = GoodsReceivedItem.objects.create(
            goods_received=goods_received,
            **item,
        )

        batch = Batch.objects.create(
            medicine=received_item.medicine,
            batch_number=received_item.batch_number,
            manufacture_date=received_item.manufacture_date,
            expiry_date=received_item.expiry_date,
            quantity=received_item.quantity,
            buying_price=received_item.buying_price,
        )

        StockMovement.objects.create(
            medicine=received_item.medicine,
            batch=batch,
            quantity=received_item.quantity,
            movement_type="IN",
            performed_by=user,
        )

    create_purchase_received_notification(
        receiver=user,
        supplier=supplier,
    )

    return goods_received