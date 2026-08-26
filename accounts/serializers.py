from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
    write_only=True,
    min_length=8
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'phone_number']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)




class CustomTokenSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token["role"] = user.role
        token["phone_number"] = user.phone_number

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        data["id"] = self.user.id
        data["username"] = self.user.username
        data["email"] = self.user.email
        data["phone_number"] = self.user.phone_number
        data["role"] = self.user.role
        data["first_name"] = self.user.first_name
        data["last_name"] = self.user.last_name

        return data



class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone_number', 'role'  ]



class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        fields = ['new_password', 'confirm_password']

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data