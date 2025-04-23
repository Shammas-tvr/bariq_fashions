from django.db import models
from category.models import Category
from django.utils.timezone import now
from decimal import Decimal

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey('category.Category', on_delete=models.CASCADE, related_name='products')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    brand = models.CharField(max_length=20, null=True, blank=True)
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def get_display_image(self):
        variant = self.variants.filter(is_active=True).first()
        if variant and variant.images.exists():
            image = variant.images.first()
            return image.get_display_image()
        return None

    def get_active_offer(self):
        """Get the best available discount (prioritizing Product Offer over Category Offer if discounts are equal)."""
        current_time = now()

        # Get Product Offer with the highest active discount
        product_offer = self.offers.filter(
            is_active=True, start_date__lte=current_time, end_date__gte=current_time
        ).order_by('-discount_percentage').first()
        product_discount = product_offer.discount_percentage if product_offer else Decimal('0.00')

        # Get Category Offer with the highest active discount
        category_offer = self.category.offers.filter(
            is_active=True, start_date__lte=current_time, end_date__gte=current_time
        ).order_by('-discount_percentage').first()
        category_discount = category_offer.discount_percentage if category_offer else Decimal('0.00')

        # Choose the highest discount, prioritizing Product Offer if equal
        if product_discount >= category_discount:
            best_discount = product_discount
            best_offer_name = product_offer.offer_name if product_offer else None
        else:
            best_discount = category_discount
            best_offer_name = category_offer.offer_name if category_offer else None

        # Apply discount if available
        if best_discount > 0:
            discounted_price = self.price - (self.price * (best_discount / Decimal('100.0')))
            return {
                'offer_price': Decimal(str(round(discounted_price, 2))),  # Convert to Decimal explicitly
                'offer_percentage': best_discount,
                'offer_name': best_offer_name
            }

        return None  # No active offer

    def update_offer_price(self):
        """Update the offer price based on the best active offer; keep the last offer price if no new offer is active."""
        active_offer = self.get_active_offer()

        if active_offer:
            new_offer_price = active_offer['offer_price']
            if self.offer_price != new_offer_price:  # Update only if there's a change
                self.offer_price = new_offer_price
                self.save(update_fields=['offer_price'])  # Save only the offer_price field



    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)  # First save to get PK

        if is_new:  # Only run this after the object is saved
            self.update_offer_price()
            super().save(update_fields=['offer_price'])  # Save only the updated field


    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    color = models.CharField(max_length=50)
    size = models.CharField(max_length=10)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} - {self.color} - {self.size}"


class Image(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def get_display_image(self):
        """Get the first active image for the variant."""
        return self.variant.images.first() if self.variant.images.exists() else None

    def __str__(self):
        return f"Image for {self.variant}"    


class ProductOffer(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='offers')
    offer_name = models.CharField(max_length=40, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def check_and_deactivate(self):
        """Deactivate the offer if the end date has passed and update product offer_price."""
        if self.end_date < now() and self.is_active:
            self.is_active = False
            self.save()  # Save the offer deactivation
            # Update the product's offer_price after deactivation
            self.product.update_offer_price()
            self.product.save()

    def save(self, *args, **kwargs):
        """Ensure expired offers are deactivated and product offer_price is updated."""
        self.check_and_deactivate()
        super(ProductOffer, self).save(*args, **kwargs)
        # After saving the offer, update the product's offer_price
        self.product.update_offer_price()
        self.product.save()

    def __str__(self):
        return f"{self.product.name} - {self.discount_percentage}%"