# Generated by Django 5.1.6 on 2025-03-08 09:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_alter_productvariant_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='brand',
            field=models.CharField(max_length=20, null=True),
        ),
    ]
