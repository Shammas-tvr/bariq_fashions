from django.db import models
# from users.models import CustomUser 

# # Create your models here.
# class Review(models.Model):
#     user=models.ForeignKey(CustomUser,on_delete=models.CASCADE)
#     product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='reviews')
#     comment = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     def __str__(self):
#         return f"Review by {self.user.username} for {self.product.name}"