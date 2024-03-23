# Generated by Django 5.0.3 on 2024-03-20 05:11

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SpotifyAccessToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_token', models.CharField(max_length=300)),
                ('expires', models.DateTimeField()),
                ('refresh_token', models.CharField(max_length=300)),
            ],
        ),
    ]