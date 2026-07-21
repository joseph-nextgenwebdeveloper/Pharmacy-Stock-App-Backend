from django.db import models

from pharmacy_config import settings

class PurchaseOrder(models.Model):
    order_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.CASCADE)
    order_date = models.DateField()
    expected_delivery_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'), ('RECEIVED', 'Received'), ('CANCELLED', 'Cancelled')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.order_number
    
class PurchaseOrderItem(models.Model):

    purchase_order = models.ForeignKey(PurchaseOrder,on_delete=models.CASCADE,related_name="items")
    medicine = models.ForeignKey("inventory.Medicine",on_delete=models.PROTECT)
    batch = models.ForeignKey("inventory.Batch", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10,decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.medicine.name} - {self.quantity}"
    
    
    
class GoodsReceived(models.Model):

    purchase_order = models.OneToOneField(
        PurchaseOrder,on_delete=models.CASCADE,
        related_name="received")
    received_date = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    notes = models.TextField(blank=True)