# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-11-10 15:12
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gtm_hit', '0004_auto_20161108_1607'),
    ]

    operations = [
        migrations.CreateModel(
            name='ValidationCode',
            fields=[
                ('validationCode', models.PositiveIntegerField(primary_key=True, serialize=False)),
            ],
        ),
        migrations.RemoveField(
            model_name='worker',
            name='id',
        ),
        migrations.RemoveField(
            model_name='worker',
            name='validationCode',
        ),
        migrations.AlterField(
            model_name='worker',
            name='workerID',
            field=models.TextField(max_length=40, primary_key=True, serialize=False),
        ),
        migrations.AddField(
            model_name='validationcode',
            name='workerID',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='gtm_hit.Worker'),
        ),
    ]
