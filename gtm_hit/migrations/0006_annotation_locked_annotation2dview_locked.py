# Generated by Django 4.1.7 on 2025-02-11 09:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gtm_hit', '0005_alter_person_unique_together_person_dataset_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='annotation',
            name='locked',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='annotation2dview',
            name='locked',
            field=models.BooleanField(default=False),
        ),
    ]
