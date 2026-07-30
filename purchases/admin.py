from django.contrib import admin
from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceived

admin.site.register(PurchaseOrder)
admin.site.register(PurchaseOrderItem)  
admin.site.register(GoodsReceived)