# Generated by Django 5.0.3 on 2024-03-23 17:23

import django.db.models.functions.text
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recordcollection', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='album',
            options={'ordering': [django.db.models.functions.text.Lower('title')]},
        ),
        migrations.AlterModelOptions(
            name='artist',
            options={'ordering': [django.db.models.functions.text.Lower('name')]},
        ),
        migrations.AlterModelOptions(
            name='genre',
            options={'ordering': [django.db.models.functions.text.Lower('name')]},
        ),
        migrations.AlterModelOptions(
            name='track',
            options={'ordering': [django.db.models.functions.text.Lower('title')]},
        ),
        migrations.RemoveField(
            model_name='track',
            name='file_hash',
        ),
    ]