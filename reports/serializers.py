from rest_framework import serializers


class InventoryReportSerializer(serializers.Serializer):
    medicine = serializers.CharField()
    sku = serializers.CharField()
    quantity = serializers.IntegerField()
    reorder_level = serializers.IntegerField()
    status = serializers.CharField()


class MonthlyMovementReportSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    stock_received = serializers.IntegerField()
    stock_dispensed = serializers.IntegerField()


class ExpiredMedicineReportSerializer(serializers.Serializer):
    medicine = serializers.CharField()
    sku = serializers.CharField()
    batch_number = serializers.CharField()
    expiry_date = serializers.DateField()
    quantity = serializers.IntegerField()


class StockValuationReportSerializer(serializers.Serializer):
    medicine = serializers.CharField()
    sku = serializers.CharField()
    quantity = serializers.IntegerField()
    stock_value = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )


class FastMovingMedicineSerializer(serializers.Serializer):
    medicine = serializers.CharField()
    sku = serializers.CharField()
    quantity_dispensed = serializers.IntegerField()


class SlowMovingMedicineSerializer(serializers.Serializer):
    medicine = serializers.CharField()
    sku = serializers.CharField()
    quantity_dispensed = serializers.IntegerField()