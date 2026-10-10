from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "receiver", "notification_type", "is_read", "is_resolved", "reminder_count")
    list_filter = ("notification_type", "is_read", "is_resolved")
