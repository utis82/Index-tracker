from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Div
from .models import Product, Part, Slice
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

# ------------------------
# 🔹 Product (Produit)
# ------------------------
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'reference_date']  # ← Ajouter reference_date
        widgets = {
            'reference_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('reference_date', css_class='col-md-6'),
            ))

# ------------------------
# 🔹 Part (Partie)
# ------------------------
class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        fields = ['name', 'reference_date']
        widgets = {
            'reference_date': forms.DateInput(attrs={'type': 'date'}),
        }

# ------------------------
# 🔹 Slice (Tranche)
# ------------------------
class SliceForm(forms.ModelForm):
    class Meta:
        model = Slice
        fields = ['label', 'component_type', 'index', 'fixed_amount', 'percentage','reference_date']
        widgets = {
            'fixed_amount': forms.NumberInput(attrs={'step': '0.01', 'class': 'fixed-field'}),
            'percentage': forms.NumberInput(attrs={'step': '0.01', 'class': 'percentage-field'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if self.user:
            self.fields['index'].queryset = self.user.userprofile.favorite_indexes.all()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(
                Row(
                    Column('label', css_class='col-md-4'),
                    Column('component_type', css_class='col-md-4'),
                    Column('index', css_class='col-md-4'),
                ),
                Row(
                    Column('fixed_amount', css_class='col-md-6'),
                    Column('percentage', css_class='col-md-6'),
                ),
                css_class='card p-3 mb-3 tranche-card position-relative',
            ))

    def clean(self):
        cleaned_data = super().clean()
        fixed = cleaned_data.get("fixed_amount")
        perc = cleaned_data.get("percentage")

        if fixed and perc:
            raise forms.ValidationError("Remplissez soit un montant (€), soit un pourcentage (%), pas les deux.")
        return cleaned_data

# ------------------------
# 🔹 Custom Formsets
# ------------------------

class CustomStructureComponentFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            for form in self.forms:
                if 'index' in form.fields:
                    form.fields['index'].queryset = self.user.userprofile.favorite_indexes.all()

class CustomSliceFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.user = self.user

    def _construct_form(self, i, **kwargs):
        kwargs["user"] = self.user
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        total = 0
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            if form.cleaned_data.get("percentage"):
                total += form.cleaned_data["percentage"]
        if total > 100:
            raise forms.ValidationError("La somme des pourcentages dépasse 100%.")

# ------------------------
# 🔹 Formsets
# ------------------------

PartFormSet = inlineformset_factory(
    Product,
    Part,
    form=PartForm,
    formset=CustomStructureComponentFormSet,
    extra=1,
    can_delete=True
)

# ------------------------
# 🔹 User Signup Form
# ------------------------

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Adresse email")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            field = self.fields[field_name]
            field.widget.attrs['class'] = 'form-input'
            field.widget.attrs['placeholder'] = field.label
