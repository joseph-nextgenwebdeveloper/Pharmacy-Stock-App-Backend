from rest_framework import serializers

from .models import GoodsReceived, GoodsReceivedItem
from .services import create_goods_received


class GoodsReceivedItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceivedItem
        fields = [
            "id", "medicine", "batch_number",
            "manufacture_date", "expiry_date",
            "quantity", "buying_price",
        ]
        read_only_fields = ["id"]


class GoodsReceivedSerializer(serializers.ModelSerializer):
    items = GoodsReceivedItemSerializer(many=True)

    class Meta:
        model = GoodsReceived
        fields = [
            "id", "supplier", "invoice_number",
            "received_date", "received_by", "notes",
            "items",
        ]
        read_only_fields = ["id", "received_date", "received_by"]

    def create(self, validated_data):
        items = validated_data.pop("items")

        return create_goods_received(
            user=self.context["request"].user,
            items=items,
            **validated_data,
        )