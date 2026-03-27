from django.db import models

class Network(models.Model):
    name = models.CharField(max_length=50)
    logo = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'networks'


class Partner(models.Model):
    type = models.CharField(max_length=20)
    name = models.CharField(max_length=50)
    description = models.TextField()
    logo = models.FileField(upload_to='partners/')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.type} - {self.name}"

    class Meta:
        db_table = 'partners'


class PartnerNetwork(models.Model):
    network = models.ForeignKey(
        Network,
        on_delete=models.PROTECT,
        db_column='network_id'
    )
    partner = models.ForeignKey(
        Partner,
        on_delete=models.PROTECT,
        db_column='partner_id'
    )
    link = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.partner} - {self.network}"

    class Meta:
        db_table = 'partners_networks'