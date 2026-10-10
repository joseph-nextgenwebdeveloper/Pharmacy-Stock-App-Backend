from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
)
from django.contrib.auth import authenticate

from .audit import log_activity
from .models import ActivityLog

User = get_user_model()


def _avatar_url(user, request=None):
    if not getattr(user, "avatar", None):
        return None
    try:
        url = user.avatar.url
    except Exception:
        return None
    return request.build_absolute_uri(url) if request is not None else url


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "phone_number",
        ]

    def create(self, validated_data):
        return User.objects.create_user(
            **validated_data
        )

class CustomTokenSerializer(TokenObtainPairSerializer):

    username_field = "email"

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token["role"] = user.role
        token["phone_number"] = user.phone_number

        return token

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError(
                "Email and password are required."
            )

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        authenticated_user = authenticate(
            username=user.username,
            password=password,
        )

        if authenticated_user is None:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        if not authenticated_user.is_active:
            raise serializers.ValidationError(
                "User account is inactive."
            )

        self.user = authenticated_user

        refresh = self.get_token(self.user)

        log_activity(self.user, ActivityLog.LOGIN, "Signed in")

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "id": self.user.id,
            "username": self.user.username,
            "email": self.user.email,
            "phone_number": self.user.phone_number,
            "role": self.user.role,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "avatar": _avatar_url(self.user, self.context.get("request")),
        }

class UserProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=15
    )
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "avatar",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "email", "role", "date_joined"]

    def validate_phone_number(self, value):
        value = (value or "").strip()
        if not value:
            return None
        clash = User.objects.filter(phone_number=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                "Another account already uses this phone number."
            )
        return value


class ActivityLogSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "user",
            "user_name",
            "user_role",
            "user_avatar",
            "action",
            "action_label",
            "summary",
            "target_type",
            "target_id",
            "target_label",
            "quantity",
            "changes",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_avatar(self, obj):
        if obj.user_id is None:
            return None
        return _avatar_url(obj.user, self.context.get("request"))


class StaffSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "name", "role", "avatar"]

    def get_avatar(self, obj):
        return _avatar_url(obj, self.context.get("request"))


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                "Passwords do not match."
            )

        return data