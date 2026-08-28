from rest_framework import serializers

from inventory.models import Batch, StockMovement

from .models import GoodsReceived, GoodsReceivedItem


class GoodsReceivedItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceivedItem
        fields = [
            "id",
            "medicine",
            "batch_number",
            "expiry_date",
            "quantity_received",
            "unit_cost",
        ]


class GoodsReceivedSerializer(serializers.ModelSerializer):
    items = GoodsReceivedItemSerializer(many=True)

    class Meta:
        model = GoodsReceived
        fields = [
            "id",
            "medicine",
            "batch_number",
            "manufacture_date",
            "expiry_date",
            "quantity_received",
            "unit_cost",
        ]

        read_only_fields = [
            "received_date",
            "received_by",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items")

        goods_received = GoodsReceived.objects.create(**validated_data)

        for item_data in items_data:

            received_item = GoodsReceivedItem.objects.create(
                goods_received=goods_received,
                **item_data
            )

            batch = Batch.objects.create(
                medicine=received_item.medicine,
                batch_number=received_item.batch_number,
                manufacture_date=received_item.manufacture_date,
                expiry_date=received_item.expiry_date,
                quantity=received_item.quantity_received,
                buying_price=received_item.unit_cost,
            )

            StockMovement.objects.create(
                medicine=received_item.medicine,
                batch=batch,
                quantity=received_item.quantity_received,
                movement_type="IN",
                performed_by=goods_received.received_by,
            )

        return goods_received