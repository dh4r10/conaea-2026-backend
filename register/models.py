import uuid
from django.db import models


class PreSale(models.Model):
    name = models.CharField(max_length=50)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'pre_sales'


class QuotaType(models.Model):
    name = models.CharField(max_length=20)
    currency = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'quota_types'


class AvailableSlot(models.Model):
    pre_sale = models.ForeignKey(
        PreSale,
        on_delete=models.PROTECT,
        db_column='pre_sale_id'
    )
    quota_type = models.ForeignKey(
        QuotaType,
        on_delete=models.PROTECT,
        db_column='quota_type_id'
    )
    mount = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.IntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.pre_sale} - {self.quota_type}"

    class Meta:
        db_table = 'available_slots'


class Registration(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    pre_sale = models.ForeignKey(
        PreSale,
        on_delete=models.PROTECT,
        db_column='pre_sale_id'
    )
    quota_type = models.ForeignKey(
        QuotaType,
        on_delete=models.PROTECT,
        db_column='quota_type_id'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.uuid}"

    class Meta:
        db_table = 'registrations'


class Transaction(models.Model):
    registration = models.ForeignKey(
        Registration,
        on_delete=models.PROTECT,
        db_column='registration_id'
    )
    payment_method = models.CharField(max_length=20)
    mount = models.DecimalField(max_digits=10, decimal_places=2)
    voucher = models.FileField(upload_to='vouchers/')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.registration} - {self.mount}"

    class Meta:
        db_table = 'transactions'


class Refund(models.Model):
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        db_column='transaction_id'
    )
    reason = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Refund - {self.transaction}"

    class Meta:
        db_table = 'refunds'