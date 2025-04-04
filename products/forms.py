from django import forms
from .models import ProductOffer


class ProductOfferForm(forms.ModelForm):
    class Meta:
        model=ProductOffer
        fields=['product','offer_name','discount_percentage','start_date','end_date','is_active']

