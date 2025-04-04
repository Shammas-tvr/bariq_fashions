from django.db import models
from users.models import CustomUser
from products.models import  ProductVariant
from orders.models import Order
from django.utils import timezone
import string,secrets


class Cart(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='carts')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    @property
    def items(self):
        return self.cartitem_set.all()
        
    def calculate_total(self):
        subtotal = sum(item.get_total() for item in self.items)
        return subtotal + self.calculate_shipping() + self.calculate_tax()

class CartItem(models.Model):
    cart = models.ForeignKey('Cart', on_delete=models.CASCADE)
    product_variant = models.ForeignKey('products.ProductVariant', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    offer_price=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def get_total(self):
        return self.product_variant.product.price * self.quantity
    

class Wallet(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    updated_at = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s wallet - Balance: {self.balance}"
    
    def add_balance(self, amount):
        self.balance += amount
        self.save()
        return True

    def deduct_balance(self, amount):
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        return False

def generate_transaction_id():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(20))

class WalletTransaction(models.Model):
    TRANSACTION_TYPE = (
        ('Credit', 'Credit'),
        ('Debit', 'Debit')
    )
    transaction_id = models.CharField(max_length=20, unique=True, editable=False, null=True)
    wallet = models.ForeignKey('Wallet', on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='wallet_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField()

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = generate_transaction_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.wallet.user.username} - {self.transaction_type} - {self.amount}"

