from django.db.models import Sum
from rest_framework import serializers

from inventory.models import Category, Medicine, Batch, StockMovement


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description"]


class MedicineSerializer(serializers.ModelSerializer):
    quantity = serializers.SerializerMethodField()
    barcode = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=64,
    )

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
            "barcode",
            "units",
            "reorder_level",
            "expiry_alert_days",
            "image",
        ]

    def get_quantity(self, obj):
        total = obj.batches.aggregate(total=Sum("quantity"))["total"]
        return total or 0

    def validate_barcode(self, value):
        value = (value or "").strip()
        if not value:
            return None

        clash = Medicine.objects.filter(barcode=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                "Another medicine already uses this barcode."
            )
        return value


class BatchSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(
        source="medicine.name", read_only=True
    )
    medicine_sku = serializers.CharField(
        source="medicine.sku", read_only=True
    )
    supplier_name = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Batch
        fields = [
            "id",
            "medicine",
            "medicine_name",
            "medicine_sku",
            "batch_number",
            "manufacture_date",
            "expiry_date",
            "quantity",
            "original_quantity",
            "buying_price",
            "selling_price",
            "supplier",
            "supplier_name",
            "status",
            "received_date",
        ]
        read_only_fields = ["received_date", "original_quantity"]
        # Uniqueness is (medicine, batch_number); the model constraint
        # produces the validator, we just give it a readable message.
        validators = []

    def get_supplier_name(self, obj):
        return obj.supplier.name if obj.supplier_id else None

    def validate(self, attrs):
        medicine = attrs.get("medicine") or getattr(self.instance, "medicine", None)
        number = attrs.get("batch_number") or getattr(
            self.instance, "batch_number", None
        )

        if medicine and number:
            clash = Batch.objects.filter(medicine=medicine, batch_number=number)
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    {
                        "batch_number": (
                            f"{medicine.name} already has a batch "
                            f"numbered {number}."
                        )
                    }
                )

        expiry = attrs.get("expiry_date") or getattr(
            self.instance, "expiry_date", None
        )
        made = attrs.get("manufacture_date") or getattr(
            self.instance, "manufacture_date", None
        )
        if made and expiry and expiry <= made:
            raise serializers.ValidationError(
                "Expiry date must be after manufacture date."
            )
        return attrs

    def update(self, instance, validated_data):
        # Stock levels only change through stock movements, so the ledger
        # always explains the number. A batch can't be re-pointed at a
        # different medicine either — a batch is one lot of one medicine.
        validated_data.pop("quantity", None)
        validated_data.pop("medicine", None)
        return super().update(instance, validated_data)


class StockMovementSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(
        source="medicine.name", read_only=True
    )
    medicine_sku = serializers.CharField(
        source="medicine.sku", read_only=True
    )
    batch_number = serializers.CharField(
        source="batch.batch_number", read_only=True
    )
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "medicine",
            "medicine_name",
            "medicine_sku",
            "batch",
            "batch_number",
            "quantity",
            "movement_type",
            "note",
            "movement_date",
            "date",
            "performed_by",
            "performed_by_name",
        ]
        read_only_fields = [
            "id",
            "movement_date",
            "date",
            "performed_by",
        ]

    def get_performed_by_name(self, obj):
        user = obj.performed_by
        return (user.get_full_name() or user.username) if user else ""

    def validate(self, attrs):
        batch = attrs.get("batch")
        medicine = attrs.get("medicine")
        if batch and medicine and batch.medicine_id != medicine.id:
            raise serializers.ValidationError(
                "That batch does not belong to this medicine."
            )
        return attrs
