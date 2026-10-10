from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = [
            "id",
            "receiver",
            "medicine",
            "medicine_name",
            "batch",
            "notification_type",
            "title",
            "message",
            "is_read",
            "is_resolved",
            "reminder_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "receiver",
            "medicine",
            "batch",
            "created_at",
            "is_resolved",
            "reminder_count",
        ]
