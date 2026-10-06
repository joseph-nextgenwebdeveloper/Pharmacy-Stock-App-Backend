from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name


class Medicine(models.Model):
    name = models.CharField(max_length=100)
    generic_name = models.CharField(max_length=100)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    sku = models.CharField(max_length=50, unique=True)
    # Manufacturer / GS1 product identifier (EAN-13, UPC-A, GTIN-14...).
    # Kept separate from the pharmacy's own `sku`: the printed barcode on
    # the pack is the source of truth for scanning, the SKU is internal.
    barcode = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    units = models.CharField(max_length=50)

    reorder_level = models.PositiveIntegerField(default=10)
    expiry_alert_days = models.PositiveIntegerField(default=30)
    image = models.ImageField(
        upload_to="medicines/",
        blank=True,
        null=True,
    )

    def save(self, *args, **kwargs):
        # Blank barcodes are stored as NULL so many medicines can have
        # "no barcode" without tripping the unique constraint.
        if self.barcode is not None:
            self.barcode = self.barcode.strip() or None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Batch(models.Model):
    """One received lot of ONE medicine."""

    STATUS_ACTIVE = "ACTIVE"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_DEPLETED = "DEPLETED"

    medicine = models.ForeignKey(
        Medicine, on_delete=models.CASCADE, related_name="batches"
    )
    batch_number = models.CharField(max_length=50)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()

    # `quantity` is the AVAILABLE quantity (it goes down as stock is sold /
    # dispensed). `original_quantity` is what was received.
    quantity = models.PositiveIntegerField()
    original_quantity = models.PositiveIntegerField(default=0)

    buying_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches",
    )
    received_date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["expiry_date", "id"]
        constraints = [
            # A lot number only has to be unique within one medicine: two
            # different products can legitimately share lot "A001".
            models.UniqueConstraint(
                fields=["medicine", "batch_number"],
                name="uniq_batch_number_per_medicine",
            )
        ]

    @property
    def status(self):
        if self.quantity <= 0:
            return self.STATUS_DEPLETED
        if self.expiry_date < timezone.localdate():
            return self.STATUS_EXPIRED
        return self.STATUS_ACTIVE

    def save(self, *args, **kwargs):
        if self._state.adding and not self.original_quantity:
            self.original_quantity = self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine.name} - {self.batch_number}"


class StockMovement(models.Model):
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField()
    movement_type = models.CharField(
        max_length=10,
        choices=[
            ("IN", "In"),
            ("OUT", "Out"),
        ]
    )
    note = models.TextField(blank=True, default="")
    movement_date = models.DateTimeField(auto_now_add=True)
    date = models.DateField(auto_now_add=True)
    performed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE
    )

    def __str__(self):
        return (
            f"{self.movement_type} - "
            f"{self.medicine.name} - "
            f"{self.quantity}"
        )