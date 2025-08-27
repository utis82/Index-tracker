from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Div
from .models import Product, Part, Slice
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import SetPasswordForm


# ------------------------
# 🔹 Product (Produit)
# ------------------------
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'part_number', 'reference_date']  # Ajout de 'part_number'
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du produit'
            }),
            'part_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de pièce (optionnel)'
            }),
            'reference_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('part_number', css_class='col-md-6'),  # Ajout de part_number
            ),
            Row(
                Column('reference_date', css_class='col-md-12'),
            )
        )


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

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user',
                               None)  # ← AJOUT : récupérer l'utilisateur
        super().__init__(*args, **kwargs)

        # AJOUT : champ product optionnel
        if self.user:
            self.fields['product'] = forms.ModelChoiceField(
                queryset=Product.objects.filter(user=self.user),
                required=False,  # ← Optionnel
                empty_label="-- Aucun produit (part indépendante) --")


# ------------------------
# 🔹 Slice (Tranche)
# ------------------------
class SliceForm(forms.ModelForm):

    class Meta:
        model = Slice
        fields = [
            'label', 'component_type', 'index', 'fixed_amount', 'percentage',
            'reference_date'
        ]
        widgets = {
            'fixed_amount':
            forms.NumberInput(attrs={
                'step': '0.01',
                'class': 'fixed-field'
            }),
            'percentage':
            forms.NumberInput(attrs={
                'step': '0.01',
                'class': 'percentage-field'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if self.user:
            self.fields[
                'index'].queryset = self.user.userprofile.favorite_indexes.all(
                )

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
            raise forms.ValidationError(
                "Remplissez soit un montant (€), soit un pourcentage (%), pas les deux."
            )
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
                    form.fields[
                        'index'].queryset = self.user.userprofile.favorite_indexes.all(
                        )


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
            raise forms.ValidationError(
                "La somme des pourcentages dépasse 100%.")


# ------------------------
# 🔹 Formsets
# ------------------------

PartFormSet = inlineformset_factory(Product,
                                    Part,
                                    form=PartForm,
                                    formset=CustomStructureComponentFormSet,
                                    extra=1,
                                    can_delete=True)

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


# ------------------------
# 🔹 Contact Form
# ------------------------


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre nom complet'
        }))
    email = forms.EmailField(widget=forms.EmailInput(
        attrs={
            'class': 'form-control',
            'placeholder': 'votre-email@exemple.com'
        }))
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sujet de votre message'
        }))
    message = forms.CharField(widget=forms.Textarea(
        attrs={
            'class': 'form-control',
            'placeholder': 'Décrivez votre question ou problème...',
            'rows': 5
        }))


# ------------------------
# 🔹 Email Verification Forms
# ------------------------


class EmailVerificationForm(forms.Form):
    """Formulaire pour saisir le code de vérification"""
    verification_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                'class': 'form-input text-center',
                'placeholder': '000000',
                'style': 'font-size: 1.5rem; letter-spacing: 0.5rem;',
                'maxlength': '6',
                'autocomplete': 'off'
            }),
        label="Code de vérification")

    def clean_verification_code(self):
        code = self.cleaned_data['verification_code']
        if not code.isdigit():
            raise ValidationError(
                'Le code doit contenir uniquement des chiffres.')
        return code


class ResendCodeForm(forms.Form):
    """Formulaire pour renvoyer un code"""
    email = forms.EmailField(widget=forms.HiddenInput())


# Modifiez votre CustomUserCreationForm existant pour désactiver le compte par défaut
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

    def clean_email(self):
        """Vérifier que l'email n'est pas déjà utilisé"""
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError('Cette adresse email est déjà utilisée.')
        return email

    def save(self, commit=True):
        """Créer le compte mais le désactiver jusqu'à vérification"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_active = False  # Désactiver jusqu'à vérification
        if commit:
            user.save()
        return user


class PasswordResetRequestForm(forms.Form):
    """Form for requesting password reset"""
    email_or_username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your email or username',
            'class': 'form-input'
        }),
        label="Email or Username")

    def clean_email_or_username(self):
        email_or_username = self.cleaned_data['email_or_username']

        # Try to find user by email first, then by username
        user = None
        if '@' in email_or_username:
            # Looks like email
            try:
                user = User.objects.get(email=email_or_username,
                                        is_active=True)
            except User.DoesNotExist:
                pass
        else:
            # Looks like username
            try:
                user = User.objects.get(username=email_or_username,
                                        is_active=True)
            except User.DoesNotExist:
                pass

        if not user:
            raise forms.ValidationError(
                "No active account found with this email or username.")

        self.user = user  # Store for later use
        return email_or_username


class PasswordResetCodeForm(forms.Form):
    """Form for entering the reset code"""
    reset_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                'placeholder':
                '000000',
                'class':
                'form-input',
                'maxlength':
                '6',
                'style':
                'text-align: center; font-size: 1.4rem; letter-spacing: 0.5rem; font-family: monospace;'
            }),
        label="Reset Code")

    def clean_reset_code(self):
        code = self.cleaned_data['reset_code']
        if not code.isdigit():
            raise forms.ValidationError("Reset code must contain only digits.")
        return code


class CustomSetPasswordForm(SetPasswordForm):
    """Custom form for setting new password"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({
            'class':
            'form-input',
            'placeholder':
            'Enter your new password'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class':
            'form-input',
            'placeholder':
            'Confirm your new password'
        })
        self.fields['new_password1'].label = "New Password"
        self.fields['new_password2'].label = "Confirm New Password"
