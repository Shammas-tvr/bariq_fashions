from django import forms
from .models import Address , Coupon,OrderReturn

class AddressForm(forms.ModelForm):
    class Meta:
        model=Address
        fields=['full_name','phone','address','city','state','pin_code','is_default']


class CheckoutForm(forms.Form):
    address= forms.ModelChoiceField(
        queryset=Address.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        required=True,
        label=' Select Shipping Address '
    )  

    def __init__(self, user=None, *args, **kwargs):  # ✅ Accept user as a parameter
        super().__init__(*args, **kwargs)  # ✅ Pass only args and kwargs to parent class
        if user:
            self.fields['address'].queryset = Address.objects.filter(user=user)


class CouponForm(forms.ModelForm):

    class Meta:
        model=Coupon

        fields=['discount','is_percentage','min_order_value','start_date','end_date','active','usage_limit','description']


class OrderReturnForm(forms.ModelForm):
    order_item_id = forms.IntegerField(required=False, widget=forms.HiddenInput())  # Optional for single item return

    class Meta:
        model = OrderReturn
        fields = ['reason']

    def clean(self):
        cleaned_data = super().clean()
        order_item_id = cleaned_data.get("order_item_id")

        if not cleaned_data.get("reason"):
            raise forms.ValidationError("Return reason is required.")

        return cleaned_data