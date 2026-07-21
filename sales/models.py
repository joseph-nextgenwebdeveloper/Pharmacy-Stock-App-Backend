from django.db import models

from django.db import models
from django.conf import settings


class Sale(models.Model):

    receipt_number = models.CharField(max_length=50,unique=True)
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,
        related_name="sales")
    total_amount = models.DecimalField(max_digits=10,decimal_places=2,default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField( max_length=20,
        choices=[
            ("CASH", "Cash"),
            ("MPESA", "M-Pesa"),
            ("CARD", "Card"),
        ]
    )
    


    def __str__(self):
        return self.receipt_number
    

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale,on_delete=models.CASCADE,related_name="items")
    medicine = models.ForeignKey("inventory.Medicine",on_delete=models.PROTECT)
    batch = models.ForeignKey("inventory.Batch",on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10,decimal_places=2)
    subtotal = models.DecimalField(max_digits=10,decimal_places=2)