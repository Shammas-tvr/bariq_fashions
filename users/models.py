from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.


class CustomUser(AbstractUser):
    email=models.EmailField()
    username=models.CharField(max_length=150,unique=True)
    date_of_joining=models.DateTimeField(auto_created=True,null=True)
    status=models.CharField(max_length=10,choices=[('Active','active'),('Blocked','blocked')],default='active')

   

    def __str__ (self):
        return self.username
        

