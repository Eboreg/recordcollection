# Generated by Django 5.0.3 on 2024-04-06 10:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recordcollection', '0004_alter_album_title_alter_artist_name_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='artist',
            name='name',
            field=models.CharField(db_index=True, max_length=500),
        ),
        migrations.AlterField(
            model_name='track',
            name='file_path',
            field=models.CharField(blank=True, db_index=True, default=None, max_length=1000, null=True),
        ),
    ]
