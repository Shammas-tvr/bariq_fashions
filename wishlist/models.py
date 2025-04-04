from django.db import models
from products.models import Product, ProductVariant
from users.models import CustomUser
from django.core.exceptions import ValidationError

class Wishlist(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="wishlist")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlist_items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE,null=True, related_name="wishlist_variants")  # Required
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product', 'variant')  # Prevent duplicate entries

    def __str__(self):
        variant_str = self.variant.color if self.variant.color else 'No Color'
        return f"{self.user.username} - {self.product.name} ({variant_str})"

    def clean(self):
        """Ensure the variant belongs to the selected product."""
        if self.variant.product != self.product:
            raise ValidationError("The variant must belong to the selected product.")

    def get_display_image(self):
        """Return the first available image from the variant."""
        if self.variant.images.exists():
            return self.variant.images.first().image.url
        return None  # Or a default static image path