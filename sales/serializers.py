from rest_framework import serializers

from .models import Sale, SaleItem
from .services import create_sale


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = [
            "id",
            "medicine",
            "batch",
            "quantity",
            "unit_price",
            "subtotal",
        ]
        read_only_fields = ["id", "subtotal"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "receipt_number",
            "sold_by",
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