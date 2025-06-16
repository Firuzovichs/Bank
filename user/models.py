from django.db import models
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import AbstractBaseUser,BaseUserManager,PermissionsMixin,Group, Permission
import secrets  # token yaratish uchun
from django.db.models.signals import post_save
from django.dispatch import receiver
class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("The Phone number must be set")
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(phone_number, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=15, unique=True)
    first_name = models.CharField(max_length=30, null=True, blank=True)
    last_name = models.CharField(max_length=30, null=True, blank=True)
    password = models.CharField(max_length=255)  # Kengaytirilgan length
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    # Customize groups and user_permissions with related_name to avoid clashes
    groups = models.ManyToManyField(
        Group, 
        related_name="customuser_set",  # Updated related_name
        blank=True
    )
    
    user_permissions = models.ManyToManyField(
        Permission, 
        related_name="customuser_permissions_set",  # Updated related_name
        blank=True
    )

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'customuser'
        verbose_name = "Foydalanuvchilar"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ('id',)
        indexes = [
            models.Index(fields=['id', 'phone_number']),
        ]

    def __str__(self):
        return self.phone_number

class MailItem(models.Model):
    batch = models.CharField(max_length=255, null=True, blank=True)  # ✅ Bo‘sh bo‘lishi mumkin
    barcode = models.CharField(max_length=50, unique=True)  # Majburiy
    weight = models.FloatField()  # Majburiy
    send_date = models.DateTimeField(null=True, blank=True)  # ✅ Bo‘sh bo‘lishi mumkin
    received_date = models.DateTimeField(null=True, blank=True)
    last_event_date = models.DateTimeField(null=True, blank=True)
    last_event_name = models.JSONField(default=list)  
    city = models.CharField(max_length=150, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_delivered = models.BooleanField(default=False)
    is_check = models.BooleanField(default=False)
    checked_name = models.CharField(max_length=255,null=True,blank=True)
    checked_time = models.DateTimeField(null=True, blank=True)  # ✅ Qo‘shildi
    checked_image = models.ImageField(upload_to='checked_images/', null=True, blank=True)  # Yangi maydon

    def __str__(self):
        return f"{self.batch} - {self.barcode}"

class BankUsers(models.Model):
    fish = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    region = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    lavozimi = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='photos/')
    token = models.CharField(max_length=64, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_hex(32)  # 64 belgili token
        super().save(*args, **kwargs)

    def __str__(self):
        return self.fish
    

class Region(models.Model):  # Viloyat
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class District(models.Model):  # Tuman
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='districts')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('region', 'name')  # Bir viloyat ichida tuman nomlari takrorlanmasin

    def __str__(self):
        return f"{self.name} ({self.region.name})"