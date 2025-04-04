from django import forms
from .models import CategoryOffer

class CategoryOfferForm(forms.ModelForm):
    class Meta:
        model = CategoryOffer
        fields = ['category', 'discount_percentage','offer_name','start_date', 'end_date', 'is_active']
