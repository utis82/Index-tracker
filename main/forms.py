from django import forms
from django.forms.models import BaseInlineFormSet
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Div, HTML
from .models import IndexedPriceStructure, StructureComponent, Assembly


class IndexedPriceStructureForm(forms.ModelForm):

    class Meta:
        model = IndexedPriceStructure
        fields = ['name', 'base_price', 'reference_date', 'assembly']
        widgets = {
            'reference_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-3'),
                Column('base_price', css_class='col-md-3'),
                Column('reference_date', css_class='col-md-3'),
                Column('assembly', css_class='col-md-3'),
            ))

        if self.user:
            self.fields['assembly'].queryset = Assembly.objects.filter(user=self.user)


class StructureComponentForm(forms.ModelForm):

    class Meta:
        model = StructureComponent
        fields = [
            'label', 'component_type', 'index', 'fixed_amount', 'percentage'
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
                    Column('index', css_class='col-md-4 index-wrapper'),
                ),
                Row(
                    Column('fixed_amount', css_class='col-md-6 fixed-wrapper'),
                    Column('percentage',
                           css_class='col-md-6 percentage-wrapper'),
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


class CustomStructureComponentFormSet(BaseInlineFormSet):

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
        print("🧪 Formset CLEAN called")
        total = 0
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            if form.cleaned_data.get("percentage"):
                total += form.cleaned_data["percentage"]

        if total < 100:
            raise forms.ValidationError(
                "La somme des pourcentages doit être exactement 100%.")
        if total > 100:
            raise forms.ValidationError("La somme des pourcentages dépasse 100%.")


StructureComponentFormSet = forms.inlineformset_factory(
    IndexedPriceStructure,
    StructureComponent,
    form=StructureComponentForm,
    formset=CustomStructureComponentFormSet,
    extra=1,
    can_delete=True)


class AssemblyForm(forms.ModelForm):

    class Meta:
        model = Assembly
        fields = ['name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False



