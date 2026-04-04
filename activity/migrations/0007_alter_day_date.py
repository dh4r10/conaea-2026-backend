from django.db import migrations, models


def datetime_to_date(apps, schema_editor):
    Day = apps.get_model('activity', 'Day')

    for day in Day.objects.all():
        if day.date:
            day.date = day.date.date()
            day.save(update_fields=['date'])


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0006_alter_activity_start_date'),
    ]

    operations = [
        migrations.RunPython(datetime_to_date),
        migrations.AlterField(
            model_name='day',
            name='date',
            field=models.DateField(),
        ),
    ]