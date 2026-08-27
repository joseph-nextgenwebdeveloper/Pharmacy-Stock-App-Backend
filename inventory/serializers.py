from rest_framework import serializers
from django.db.models import Sum
from inventory.models import Category, Medicine, Batch, StockMovement


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class MedicineSerializer(serializers.ModelSerializer):
    quantity = serializers.SerializerMethodField()

    class Meta:
        model = Medicine
        fields = [
            "id",
            "name",
            "generic_name",
            "description",
            "quantity",
            "category",
            "sku",
            "units",
        ]

    def get_quantity(self, obj):
        total = obj.batch_set.aggregate(total=Sum("quantity"))["total"]
        return total or 0



class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = [
            'id',
            'medicine',
            'batch_number',
            'manufacture_date',
            'expiry_date',
            'quantity',
            'buying_price',
            'received_date',
        ]
        read_only_fields = ['received_date']

    def validate(self, attrs):
        if attrs['expiry_date'] <= attrs['manufacture_date']:
            raise serializers.ValidationError(
                "Expiry date must be after manufacture date."
            )
        return attrs



class StockMovementSerializer(serializers.ModelSerializer):

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "medicine",
            "batch",
            "quantity",
            "movement_type",
            "movement_date",
            "date",
        ]

        read_only_fields = [
            "movement_date",
            "date",
        ]

