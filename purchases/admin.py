from django.contrib import admin

from .models import GoodsReceived, GoodsReceivedItem


admin.site.register(GoodsReceived)
admin.site.register(GoodsReceivedItem)