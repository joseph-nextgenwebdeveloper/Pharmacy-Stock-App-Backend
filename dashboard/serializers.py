from rest_framework import serializers


class DayMovementSerializer(serializers.Serializer):
    date = serializers.CharField()
    units_in = serializers.IntegerField()
    units_out = serializers.IntegerField()


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
    expired_batches = serializers.IntegerField()
    expiring_batches = serializers.IntegerField()
    weekly_movements = DayMovementSerializer(many=True)
    my_updates_today = serializers.IntegerField()
