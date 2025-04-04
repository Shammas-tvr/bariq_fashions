from django.db import models
from django.utils.timezone import now

class Category(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('blocked', 'Blocked'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='category_images/', null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Fixed typo and added auto update

    class Meta:
       db_table = 'Category'

    def __str__(self):
        return self.name


class CategoryOffer(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='offers')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    offer_name = models.CharField(max_length=30, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.category.name} - {self.discount_percentage}%"

    def check_and_deactivate(self):
        """Check if the offer has expired and deactivate it."""
        if self.end_date < now():
            self.is_active = False
            self.save()

    def save(self, *args, **kwargs):
        """Ensure expired offers are deactivated and update related product offer prices."""
        self.check_and_deactivate()
        super().save(*args, **kwargs)  # Save the offer first

        # Update offer price for all products in this category
        for product in self.category.products.all():
            product.update_offer_price()  # Update offer price based on the latest offers

