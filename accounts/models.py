from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ("ADMIN", "Admin"),
        ("PHARMACIST", "Pharmacist"),
        ("STOCK_CLERK", "Stock Clerk"),
        ("STORE_MANAGER", "Store Manager"),
    ]
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="STOCK_CLERK")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    @property
    def display_name(self):
        return self.get_full_name().strip() or self.username

    def __str__(self):
        return self.username


class ActivityLog(models.Model):
    """Who did what, and when.

    One row per meaningful action (stock in/out, creating or editing a
    medicine / batch / supplier, signing in...). The user's name and role are
    copied onto the row so the history still reads correctly if the account
    is renamed or removed later.
    """

    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    STOCK_IN = "STOCK_IN"
    STOCK_OUT = "STOCK_OUT"
    GOODS_RECEIVED = "GOODS_RECEIVED"
    SALE_CREATED = "SALE_CREATED"
    MEDICINE_CREATED = "MEDICINE_CREATED"
    MEDICINE_UPDATED = "MEDICINE_UPDATED"
    MEDICINE_DELETED = "MEDICINE_DELETED"
    BATCH_CREATED = "BATCH_CREATED"
    BATCH_UPDATED = "BATCH_UPDATED"
    BATCH_DELETED = "BATCH_DELETED"
    CATEGORY_CREATED = "CATEGORY_CREATED"
    SUPPLIER_CREATED = "SUPPLIER_CREATED"
    SUPPLIER_UPDATED = "SUPPLIER_UPDATED"

    ACTION_CHOICES = [
        (LOGIN, "Signed in"),
        (LOGOUT, "Signed out"),
        (PROFILE_UPDATED, "Profile updated"),
        (STOCK_IN, "Stock in"),
        (STOCK_OUT, "Stock out"),
        (GOODS_RECEIVED, "Delivery received"),
        (SALE_CREATED, "Dispensing recorded"),
        (MEDICINE_CREATED, "Medicine added"),
        (MEDICINE_UPDATED, "Medicine edited"),
        (MEDICINE_DELETED, "Medicine deleted"),
        (BATCH_CREATED, "Batch created"),
        (BATCH_UPDATED, "Batch edited"),
        (BATCH_DELETED, "Batch deleted"),
        (CATEGORY_CREATED, "Category added"),
        (SUPPLIER_CREATED, "Supplier added"),
        (SUPPLIER_UPDATED, "Supplier edited"),
    ]

    # Rows that are bookkeeping rather than an "update" the person made.
    NOT_UPDATES = (LOGIN, LOGOUT, PROFILE_UPDATED, GOODS_RECEIVED, SALE_CREATED)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    user_name = models.CharField(max_length=150, blank=True)
    user_role = models.CharField(max_length=20, blank=True)

    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    summary = models.CharField(max_length=255)

    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    target_label = models.CharField(max_length=255, blank=True)

    # Signed units for stock actions (+in / -out). Null for everything else,
    # so summing it gives "net units".
    quantity = models.IntegerField(null=True, blank=True)

    # {"field": {"from": old, "to": new}} for edits; free-form extra detail
    # (batch number, reason, reference, balance before/after) for stock.
    changes = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.user_name or 'system'}: {self.summary}"
