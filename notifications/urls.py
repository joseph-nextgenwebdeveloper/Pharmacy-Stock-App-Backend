from django.urls import path

from .views import NotificationViewSet


urlpatterns = [
    path("", NotificationViewSet.as_view({"get": "list"}), name="notification-list"),
    path("<int:pk>/", NotificationViewSet.as_view({"get": "retrieve"}), name="notification-detail"),
    path("<int:pk>/mark-as-read/", NotificationViewSet.as_view({"patch": "mark_as_read"}), name="notification-mark-as-read"),
]