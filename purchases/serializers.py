from rest_framework import serializers

from .models import GoodsReceived, GoodsReceivedItem
from .services import create_goods_received


class GoodsReceivedItemSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)

    class Meta:
        model = GoodsReceivedItem
        fields = [
            "id", "medicine", "medicine_name", "batch_number",
            "manufacture_date", "expiry_date",
            "quantity", "buying_price", "selling_price",
        ]
        read_only_fields = ["id"]


class GoodsReceivedSerializer(serializers.ModelSerializer):
    items = GoodsReceivedItemSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    received_by_name = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()

    def get_received_by_name(self, obj):
        return obj.received_by.display_name if obj.received_by_id else ""

    def get_reference(self, obj):
        return f"GRN-{obj.id}"

    class Meta:
        model = GoodsReceived
        fields = [
            "id", "reference", "supplier", "supplier_name", "invoice_number",
            "received_date", "received_by", "received_by_name", "notes",
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