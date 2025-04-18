from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.


class CustomUser(AbstractUser):
    email=models.EmailField()
    username=models.CharField(max_length=150,unique=True)
    date_of_joining=models.DateTimeField(auto_created=True,null=True)
    is_blocked=models.BooleanField(default=False)

   

    def __str__ (self):
        return self.username
        

