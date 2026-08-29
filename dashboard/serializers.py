from rest_framework import serializers


class DashboardSerializer(serializers.Serializer):
    total_medicines = serializers.IntegerField()
    total_stock = serializers.IntegerField()
    healthy_stock = serializers.IntegerField()
    low_stock = serializers.IntegerField()
    out_of_stock = serializers.IntegerField()
    today_received = serializers.IntegerField()
    today_dispensed = serializers.IntegerField()
    today_sales = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()