import datetime

from django import forms
from django.forms import ValidationError
from django.forms.widgets import SelectDateWidget
from django.utils.translation import gettext as _

from ..models import VoucherPurpose


class VoucherGenerationForm(forms.Form):
    number_of_vouchers = forms.IntegerField(label=_("How many voucher should be generated?"), initial=20)
    percentage = forms.IntegerField(label=_('Reduction in percent (0-100).'), required=False)
    amount = forms.IntegerField(label=_('Value of the voucher in CHF.'), required=False)
    purpose = forms.ModelChoiceField(queryset=VoucherPurpose.objects)
    expires_flag = forms.BooleanField(label=_("Set expire date?"), initial=False, required=False)
    expires = forms.DateField(widget=SelectDateWidget, initial=datetime.date.today() + datetime.timedelta(days=365))

    def clean(self) -> dict:
        cleaned_data = super().clean()

        amount = cleaned_data.get('amount')
        percentage = cleaned_data.get('percentage')

        if not amount and not percentage:
            raise ValidationError('You need to set either the amount or percentage.')
        if amount and percentage:
            raise ValidationError('You are not allowed to set both amount and percentage.')

        return cleaned_data

    def clean_amount(self) -> dict:
        amount = self.cleaned_data.get('amount')
        if amount and amount < 0:
            raise ValidationError('The amount must be non-negative')
        return amount

    def clean_percentage(self) -> dict:
        percentage = self.cleaned_data.get('percentage')
        if percentage and (percentage < 0 or percentage > 100):
            raise ValidationError('The percentage must be between 0 and 100')
        return percentage
