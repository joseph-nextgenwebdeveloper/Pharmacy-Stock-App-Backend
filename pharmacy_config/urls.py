from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as serve_media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),  
    path('api/inventory/', include('inventory.urls')),
    path("api/purchases/", include("purchases.urls")),
    path("api/sales/", include("sales.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/reports/", include("reports.urls")),
    path("api/suppliers/", include("suppliers.urls")),
]

# Medicine photos. `static()` only works when DEBUG=True, so on Render
# (DEBUG=False) every /media/... URL returned 404 and no photo ever showed.
# This serves them in production too. (When CLOUDINARY_URL is set the image
# URLs point at Cloudinary and this route is simply never hit.)
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        serve_media,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
