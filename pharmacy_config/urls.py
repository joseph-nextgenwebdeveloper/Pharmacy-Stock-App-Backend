from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),  
    path('api/inventory/', include('inventory.urls')),
    path("api/purchases/", include("purchases.urls")),
    path("api/sales/", include("sales.urls")),
]
