from django.db import models
from django.conf import settings


class GoodsReceived(models.Model):
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.PROTECT,
        related_name="deliveries",
    )
    invoice_number = models.CharField(max_length=100, blank=True)
    received_date = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Delivery {self.id} - {self.supplier.name}"


class GoodsReceivedItem(models.Model):
    goods_received = models.ForeignKey(
        GoodsReceived,
        related_name="items",
        on_delete=models.CASCADE,
    )
    medicine = models.ForeignKey(
        "inventory.Medicine",
        on_delete=models.PROTECT,
    )
    batch_number = models.CharField(max_length=50)
    manufacture_date = models.DateField()
    expiry_date = models.DateField()
    quantity = models.PositiveIntegerField()
    buying_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    def __str__(self):
        return f"{self.medicine.name} ({self.batch_number})"