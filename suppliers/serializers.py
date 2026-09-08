from rest_framework import serializers

from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "company_name",
            "contact_person",
            "email",
            "phone_number",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        queryset = Supplier.objects.filter(name__iexact=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "A supplier with this name already exists."
            )

        return value

    def validate_phone_number(self, value):
        value = value.strip()

        if len(value) < 10:
            raise serializers.ValidationError(
                "Enter a valid phone number."
            )

        return value

    def validate_email(self, value):
        if value:
            queryset = Supplier.objects.filter(email__iexact=value)

            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise serializers.ValidationError(
                    "This email is already in use."
                )

        return value