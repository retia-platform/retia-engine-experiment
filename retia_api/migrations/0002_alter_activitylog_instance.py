# Generated by Django 5.0.1 on 2024-04-04 08:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retia_api', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activitylog',
            name='instance',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
