# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-18 13:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marker', '0002_auto_20161013_1455'),
    ]

    operations = [
        migrations.CreateModel(
            name='Rectanges',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cameraID', models.PositiveSmallIntegerField(default=0)),
                ('rectangleID', models.PositiveIntegerField(default=0)),
                ('x1', models.PositiveSmallIntegerField(default=0)),
                ('y1', models.PositiveSmallIntegerField(default=0)),
                ('x2', models.PositiveSmallIntegerField(default=0)),
                ('y2', models.PositiveSmallIntegerField(default=0)),
            ],
        ),
    ]
