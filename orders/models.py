from django.db import models
from users.models import CustomUser 
from products.models import ProductVariant
from django.utils.timezone import now
from django.utils import timezone
import uuid
from decimal import Decimal
# Create your models here.


class ShippingAddress(models.Model):
    full_name=models.CharField(max_length=100)
    phone=models.CharField(max_length=13)
    address=models.TextField()
    city=models.CharField(max_length=30)
    state=models.CharField(max_length=30)
    pin_code=models.CharField(max_length=10)
    is_default=models.BooleanField(default=False)
 
    def __str__(self):
        return f"{self.full_name},{self.address},{self.city}"


class Address(models.Model):
    user=models.ForeignKey(CustomUser,on_delete=models.CASCADE)
    full_name=models.CharField(max_length=100)
    phone=models.CharField(max_length=13)
    address=models.TextField()
    city=models.CharField(max_length=30)
    state=models.CharField(max_length=30)
    pin_code=models.CharField(max_length=10)
    is_default=models.BooleanField(default=False)   


    def __str__(self):
        return f"{self.full_name},{self.address},{self.city}" 
    
#_________________________________________________________________________________________#

# coupon applying

def generate_coupon_code():
    return uuid.uuid4().hex[:8].upper()

class Coupon(models.Model):
    code = models.CharField(max_length=30, unique=True, default=generate_coupon_code)
    discount = models.DecimalField(max_digits=10, decimal_places=2)
    is_percentage = models.BooleanField(default=False)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) 
    start_date = models.DateTimeField(default=now)  
    end_date = models.DateTimeField()
    active = models.BooleanField(default=True) 
    usage_limit=models.PositiveBigIntegerField(default=1)
    description=models.CharField(max_length=150,null=True)

    def is_valid(self):
        return self.active and self.start_date <= now() <= self.end_date        
    
    def __str__(self):
        return self.code 
    
class  CouponUsage(models.Model):
    user=models.ForeignKey(CustomUser,on_delete=models.CASCADE)
    coupon=models.ForeignKey(Coupon,on_delete=models.CASCADE)
    used_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}-{self.coupon.code}"    
    


class Order(models.Model):
    order_id = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    address = models.ForeignKey("ShippingAddress", on_delete=models.PROTECT)
    order_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(
        max_length=50,
        choices=[('COD', 'Cash on Delivery'), ('Online', 'Online Payment')],
        default='COD'
    )
    coupon = models.ForeignKey("Coupon", on_delete=models.SET_NULL, null=True, blank=True)
    product_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)   
    razorpay_order_id = models.CharField(max_length=50, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=50, blank=True, null=True)
    razorpay_signature = models.TextField(blank=True, null=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        if not self.order_id:
            prefix = "COD" if self.payment_method == "COD" else "ORD"
            unique_id = uuid.uuid4().hex[:8].upper()
            self.order_id = f"{prefix}-{unique_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_id} - {self.user.username}"


class OrderItem(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('return_requested', 'Return Requested'),
        ('return_approved', 'Return Approved'),
        ('return_rejected', 'Return Rejected'),
        ('return_received', 'Return Received'),
        ('return_processed', 'Return Processed'),
        ('refunded', 'Refunded'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def get_product_image(self):
        product_image = self.product_variant.images.first()
        return product_image.image.url if product_image else None


#___________________________________________________________________________________________________________________________#

# order return


class OrderReturn(models.Model):
    user=models.ForeignKey(CustomUser,on_delete=models.CASCADE)
    order=models.ForeignKey(Order,on_delete=models.CASCADE)
    order_item=models.ForeignKey(OrderItem,on_delete=models.SET_NULL,null=True,blank=True)
    reason=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    update_at=models.DateTimeField(auto_now=True)

    def __str__(self):
        return f" Return request for order {self.order.order_id} - {self.return_status}"


