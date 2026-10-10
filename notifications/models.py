from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    LOW_STOCK = "LOW_STOCK", "Low Stock"
    OUT_OF_STOCK = "OUT_OF_STOCK", "Out of Stock"
    MEDICINE_EXPIRED = "MEDICINE_EXPIRED", "Medicine Expired"
    MEDICINE_EXPIRING = "MEDICINE_EXPIRING", "Medicine Expiring Soon"
    PURCHASE_RECEIVED = "PURCHASE_RECEIVED", "Purchase Order Received"
    PURCHASE_CANCELLED = "PURCHASE_CANCELLED", "Purchase Order Cancelled"


class Notification(models.Model):
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    medicine = models.ForeignKey(
        "inventory.Medicine",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    batch = models.ForeignKey(
        "inventory.Batch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    # created_at is bumped each time a still-open alert is repeated, so the
    # newest reminder always sits at the top of the feed.
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=255, blank=True, null=True)

    # An alert stays "open" (and keeps being repeated) until the problem is
    # fixed — e.g. an out-of-stock alert is resolved when stock comes in.
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    reminder_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.receiver.email} - {self.notification_type}"
