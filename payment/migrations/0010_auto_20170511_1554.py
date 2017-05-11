# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-05-11 15:54
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0009_auto_20170227_1123'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='comment',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='credit_debit',
            field=models.CharField(choices=[('unknown', 'unknown'), ('credit', 'credit (incoming money)'), ('debit', 'debit (outgoing money)')], default='unknown', help_text='If this transaction is a credit or a debit.', max_length=50),
        ),
    ]
