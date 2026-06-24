from django import forms


class ServiceUserForm(forms.Form):
    service_user_name = forms.CharField(
        label="Full name of the person attending",
        max_length=300,
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. John Smith",
                "class": "form-control form-control-lg",
            }
        ),
        help_text="Enter the full name of the service user who will be attending the activity.",
    )

    def clean_service_user_name(self):
        name = self.cleaned_data["service_user_name"]
        if len(name.strip()) < 2:
            raise forms.ValidationError("Please enter a full name (at least 2 characters).")
        return name


class ActivityForm(forms.ModelForm):
    price_pounds = forms.DecimalField(
        label="Price per person (\u00a3)",
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "step": "0.50",
                "class": "form-control",
                "placeholder": "e.g. 12.50",
            }
        ),
        help_text="Enter the price in pounds. For example: 10.50 for \u00a310.50, or 25 for \u00a325.",
    )

    class Meta:
        from .models import Activity

        model = Activity
        fields = [
            "name",
            "description",
            "price_pounds",
            "start_date",
            "max_spaces",
            "payment_closes_at",
            "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "payment_closes_at": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Describe the activity so parents/carers know what to expect...",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Beach Trip to Brighton",
                }
            ),
            "max_spaces": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Leave blank for unlimited",
                }
            ),
        }
        labels = {
            "name": "Activity name",
            "description": "Description (optional)",
            "start_date": "Activity date",
            "max_spaces": "Maximum number of spaces (optional)",
            "payment_closes_at": "Payment closing date (optional)",
            "is_active": "Make this activity visible to parents/carers?",
        }
        help_texts = {
            "max_spaces": "If this activity has limited places, enter the maximum here. Leave blank if there is no limit.",
            "is_active": "Uncheck to hide this activity from the public payment page.",
            "start_date": "When will this activity take place?",
            "payment_closes_at": "If set, payments will not be accepted on or after this date. Useful to prevent last-minute bookings.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["price_pounds"].initial = self.instance.price_pounds
        self.fields["is_silva_care_wide"] = forms.BooleanField(
            label="Make this available across all sites (Silva Care Wide)",
            required=False,
            initial=self.instance.is_company_wide if self.instance and self.instance.pk else False,
            widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
            help_text="Check this to allow parents and carers from any site to book this activity.",
        )

    def clean_price_pounds(self):
        price = self.cleaned_data["price_pounds"]
        if price <= 0:
            raise forms.ValidationError("Price must be greater than \u00a30.")
        if price > 99999:
            raise forms.ValidationError("Price seems too high. Please check the amount.")
        return price

    def save(self, commit=True):
        self.instance.price_pennies = int(self.cleaned_data["price_pounds"] * 100)
        return super().save(commit=commit)


class HeadofficeActivityForm(ActivityForm):
    class Meta(ActivityForm.Meta):
        fields = [
            "site",
            "name",
            "description",
            "price_pounds",
            "start_date",
            "max_spaces",
            "payment_closes_at",
            "is_active",
        ]
        labels = {
            **ActivityForm.Meta.labels,
            "site": "Site",
        }
        help_texts = {
            **ActivityForm.Meta.help_texts,
            "site": "Choose a site for this activity, or leave blank to make it available across all sites.",
        }
        widgets = {
            **ActivityForm.Meta.widgets,
            "site": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        site_field = self.fields["site"]
        site_field.required = False
        site_field.empty_label = "Silva Care Wide"
        site_field.queryset = Site.objects.all()
