# Generated by Django 5.0.1 on 2024-01-09 08:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retia_api', '0004_device_created_at_device_modified_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]