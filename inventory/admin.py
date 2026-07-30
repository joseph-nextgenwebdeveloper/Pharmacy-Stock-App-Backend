from django.contrib import admin
from .models import Category, Medicine, Batch, StockMovement

admin.site.register(Category)
admin.site.register(Medicine)
admin.site.register(Batch)
admin.site.register(StockMovement)