# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-11-10 17:06
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gtm_hit', '0008_auto_20161110_1705'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='validationcode',
            name='workerID',
        ),
    ]
