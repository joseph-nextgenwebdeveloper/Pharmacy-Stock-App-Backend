from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name
    
    
class Medicine(models.Model):
    name = models.CharField(max_length=100)
    generic_name = models.CharField(max_length=100)
    description = models.TextField()
    quantity = models.PositiveIntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    sku = models.CharField(max_length=50, unique=True)
    units = models.CharField(max_length=50)
    def __str__(self):
        return self.name
    
    
class Batch(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    batch_number = models.CharField(max_length=50, unique=True)
    manufacture_date = models.DateField()
    expiry_date = models.DateField()
    quantity = models.PositiveIntegerField()
    buying_price = models.DecimalField(max_digits=10, decimal_places=2)
    received_date = models.DateField(auto_now_add=True) 
    def __str__(self):
        return f"{self.medicine.name} - {self.batch_number}"
    

class StockMovement(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    movement_type = models.CharField(max_length=10, choices=[('IN', 'In'), ('OUT', 'Out')])
    movement_date = models.DateTimeField(auto_now_add=True)
    date = models.DateField(auto_now_add=True)
    performed_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.movement_type} - {self.medicine.name} - {self.quantity}"