from rest_framework import serializers
from django.contrib.auth import get_user_model

from rest_framework import serializers
from .models import BankUsers,MailItem


class CheckedMailItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailItem
        fields = ['barcode', 'checked_name', 'checked_time']

class BankUsersProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankUsers
        fields = '__all__'


class TokenObtainPairSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')
        password = attrs.get('password')

        user = get_user_model().objects.get(phone_number=phone_number)
        
        if user and user.check_password(password):
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)
            return {'access': str(refresh.access_token), 'refresh': str(refresh),'phone_number': user.phone_number}
        else:
            raise serializers.ValidationError("Invalid phone number or password.")
        

class MailItemSerializer(serializers.ModelSerializer):
    checked_image = serializers.ImageField(read_only=True)  # URL shaklida bo‘ladi yoki null
    checked_time = serializers.DateTimeField(read_only=True)
    checked_name = serializers.CharField(read_only=True)

    class Meta:
        model = MailItem
        fields = [
            'barcode', 'send_date',
            'received_date', 'last_event_date',
            'city','is_check',
            'checked_name', 'checked_time', 'checked_image'
        ]