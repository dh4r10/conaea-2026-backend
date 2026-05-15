from rest_framework import serializers
from .models import PreSale, QuotaType, AvailableSlot, Registration, Transaction, Refund, DynamicCode


class PreSaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreSale
        fields = '__all__'

    def validate(self, data):
        start = data.get('start_date', getattr(self.instance, 'start_date', None))
        end = data.get('end_date', getattr(self.instance, 'end_date', None))

        if start and end and start >= end:
            raise serializers.ValidationError(
                {'end_date': 'La fecha de fin debe ser posterior a la fecha de inicio.'}
            )

        if start and end:
            qs = PreSale.objects.filter(
                is_active=True,
                start_date__lt=end,
                end_date__gt=start,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                names = ', '.join(qs.values_list('name', flat=True))
                raise serializers.ValidationError(
                    {'non_field_errors': f'El rango de fechas se cruza con: {names}.'}
                )

        return data


class QuotaTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotaType
        fields = '__all__'


class AvailableSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailableSlot
        fields = '__all__'


class AvailableSlotDetailSerializer(serializers.ModelSerializer):
    pre_sale = PreSaleSerializer(read_only=True)
    quota_type = QuotaTypeSerializer(read_only=True)

    class Meta:
        model = AvailableSlot
        fields = '__all__'


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = '__all__'


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'

    def validate_voucher(self, value):
        valid_extensions = ('.jpg', '.jpeg', '.png')
        if not value.name.lower().endswith(valid_extensions):
            raise serializers.ValidationError('Solo se permiten imágenes JPG o PNG')
        if value.size > 500 * 1024:
            raise serializers.ValidationError('La imagen no debe superar los 500 KB')
        return value

class TransactionDetailSerializer(serializers.ModelSerializer):
    refund = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = '__all__'

    def get_refund(self, obj):
        refund = Refund.objects.filter(transaction=obj, is_active=True).first()
        if refund:
            return RefundSerializer(refund).data
        return None


class RegistrationSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(format='hex_verbose', read_only=True)

    class Meta:
        model = Registration
        fields = '__all__'


class RegistrationDetailSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(format='hex_verbose', read_only=True)
    pre_sale = PreSaleSerializer(read_only=True)
    quota_type = QuotaTypeSerializer(read_only=True)
    transactions = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = '__all__'

    def get_transactions(self, obj):
        transactions = Transaction.objects.filter(
            registration=obj,
            is_active=True
        )
        return TransactionDetailSerializer(transactions, many=True).data

    def get_balance(self, obj):
        from django.db.models import Sum, Q

        # Total pagado (sin refunds)
        total_paid = Transaction.objects.filter(
            registration=obj,
            is_active=True
        ).exclude(
            id__in=Refund.objects.values('transaction_id')
        ).aggregate(Sum('mount'))['mount__sum'] or 0

        # Total devuelto
        total_refunded = Transaction.objects.filter(
            registration=obj,
            is_active=True,
            id__in=Refund.objects.values('transaction_id')
        ).aggregate(Sum('mount'))['mount__sum'] or 0

        # Monto requerido desde available_slots
        try:
            slot = AvailableSlot.objects.get(
                pre_sale=obj.pre_sale,
                quota_type=obj.quota_type
            )
            required = slot.mount
        except AvailableSlot.DoesNotExist:
            required = 0

        return {
            'required': required,
            'paid': total_paid,
            'refunded': total_refunded,
            'pending': max(required - total_paid + total_refunded, 0),
            'overpaid': max(total_paid - total_refunded - required, 0)
        }
    
# serializers.py
class DynamicCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicCode
        fields = '__all__'

class DynamicCodeDetailSerializer(serializers.ModelSerializer):
    quota_type = QuotaTypeSerializer(read_only=True)

    class Meta:
        model = DynamicCode
        fields = '__all__'