# Generated by Django 5.1.6 on 2025-04-01 08:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0042_alter_coupon_code'),
    ]

    operations = [
        migrations.RenameField(
            model_name='order',
            old_name='discount_amount',
            new_name='coupon_discount',
        ),
        migrations.RenameField(
            model_name='order',
            old_name='total_discount',
            new_name='product_discount',
        ),
    ]
