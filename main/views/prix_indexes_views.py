from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from main.forms import IndexedPriceStructureForm, StructureComponentFormSet
from main.models import IndexedPriceStructure


@login_required
def prix_indexes_view(request):
    structure = IndexedPriceStructure(user=request.user)

    if request.method == "POST":
        form = IndexedPriceStructureForm(request.POST)
        formset = StructureComponentFormSet(request.POST, user=request.user, instance=structure)

        if form.is_valid() and formset.is_valid():
            structure = form.save(commit=False)
            structure.user = request.user
            structure.save()
            formset.instance = structure
            formset.save()
            return redirect('main:prix_indexes')

    else:
        form = IndexedPriceStructureForm()
        formset = StructureComponentFormSet(user=request.user, instance=structure)

    structures = IndexedPriceStructure.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'prix_indexes.html', {
        'form': form,
        'formset': formset,
        'structures': structures,
    })
