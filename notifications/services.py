from .models import Notification, NotificationType

def create_notification(receiver, notification_type, message, title=None, medicine=None):
    notification = Notification.objects.filter(
        receiver=receiver, medicine=medicine,
        notification_type=notification_type, is_read=False
    ).first()

    if notification:
        return notification

    return Notification.objects.create(
        receiver=receiver, medicine=medicine,
        notification_type=notification_type,
        title=title, message=message,
    )


def create_low_stock_notification(receiver, medicine, quantity, reorder_level):
    return create_notification(
        receiver=receiver, medicine=medicine,
        notification_type=NotificationType.LOW_STOCK,
        title="Low Stock Alert",
        message=(
            f"{medicine.name} is running low. "
            f"Current stock: {quantity}. "
            f"Reorder level: {reorder_level}."
        ),
    )


def create_out_of_stock_notification(receiver, medicine):
    return create_notification(
        receiver=receiver, medicine=medicine,
        notification_type=NotificationType.OUT_OF_STOCK,
        title="Out of Stock",
        message=f"{medicine.name} is out of stock.",
    )


def create_expired_notification(receiver, medicine, batch):
    return create_notification(receiver=receiver, medicine=medicine,
        notification_type=NotificationType.MEDICINE_EXPIRED,
        title="Medicine Expired",
        message=f"{medicine.name}, batch {batch.batch_number}, has expired.",
    )


def create_expiring_notification(receiver, medicine, batch):
    return create_notification(
        receiver=receiver, medicine=medicine,
        notification_type=NotificationType.MEDICINE_EXPIRING,
        title="Medicine Expiring Soon",
        message=f"{medicine.name}, batch {batch.batch_number}, expires on {batch.expiry_date}.",
    )


def create_purchase_received_notification(receiver, supplier):
    return create_notification(
        receiver=receiver,
        notification_type=NotificationType.PURCHASE_RECEIVED,
        title="Purchase Received",
        message=f"Stock delivery from {supplier.name} has been received.",
    )


def create_purchase_cancelled_notification(receiver, supplier):
    return create_notification(
        receiver=receiver,
        notification_type=NotificationType.PURCHASE_CANCELLED,
        title="Purchase Cancelled",
        message=f"Stock delivery from {supplier.name} has been cancelled.",
    )