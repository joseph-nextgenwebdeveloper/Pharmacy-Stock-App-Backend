from rest_framework import serializers

from .models import Sale, SaleItem
from .services import create_sale


class SaleItemSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "medicine",
            "medicine_name",
            "batch",
            "batch_number",
            "quantity",
            "unit_price",
            "subtotal",
        ]
        read_only_fields = ["id", "subtotal"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    sold_by_name = serializers.SerializerMethodField()

    def get_sold_by_name(self, obj):
        return obj.sold_by.display_name if obj.sold_by_id else ""

    class Meta:
        model = Sale
        fields = [
            "id",
            "receipt_number",
            "sold_by",
            "sold_by_name",
            "total_amount",
            "payment_method",
            "created_at",
            "items",
        ]
        read_only_fields = [
            "id",
            "sold_by",
            "total_amount",
            "created_at",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items")

        sale = create_sale(
            user=self.context["request"].user,
            receipt_number=validated_data["receipt_number"],
            payment_method=validated_data["payment_method"],
            items=items_data,
        )

        return sale