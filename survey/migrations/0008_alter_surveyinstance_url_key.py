# Generated by Django 3.2.12 on 2022-04-03 11:00

from django.db import migrations, models
import utils.code_generator


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0007_surveyinstance_is_completed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='surveyinstance',
            name='url_key',
            field=models.CharField(default=utils.code_generator.CodeGenerator.short_uuid, max_length=32, unique=True),
        ),
    ]
