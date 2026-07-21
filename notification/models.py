from django.db import models

from pharmacy_config import settings

class NotificationType(models.TextChoices):
    LOW_STOCK = "LOW_STOCK", "Low Stock"
    OUT_OF_STOCK = "OUT_OF_STOCK", "Out of Stock"
    MEDICINE_EXPIRED = "MEDICINE_EXPIRED", "Medicine Expired"
    MEDICINE_EXPIRING = "MEDICINE_EXPIRING", "Medicine Expiring Soon"
    PURCHASE_RECEIVED = "PURCHASE_RECEIVED", "Purchase Order Received"
    PURCHASE_CANCELLED = "PURCHASE_CANCELLED", "Purchase Order Cancelled"
    
    
class Notification(models.Model):
    receiver =models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE  )
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)    
    title = models.CharField(max_length=255, blank=True, null=True)