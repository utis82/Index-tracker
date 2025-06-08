from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from main.forms import IndexedPriceStructureForm, StructureComponentFormSet
from main.models import IndexedPriceStructure


@login_required
def prix_indexes_view(request):
    prefix = "components"

    if request.method == "POST":
        print("📥 POST reçu")
        structure_id = request.POST.get("structure_id")
        print("📩 structure_id POST reçu:", structure_id)

        structure = None

        if structure_id:
            try:
                structure = IndexedPriceStructure.objects.get(id=structure_id, user=request.user)
                form = IndexedPriceStructureForm(request.POST, instance=structure)
            except IndexedPriceStructure.DoesNotExist:
                structure = IndexedPriceStructure(user=request.user)
                form = IndexedPriceStructureForm(request.POST)
        else:
            structure = IndexedPriceStructure(user=request.user)
            form = IndexedPriceStructureForm(request.POST)

        if form.is_valid():
            print("✅ Formulaire principal valide")

            if structure_id:
                structure = form.save()
                structure.components.all().delete()
            else:
                structure = form.save(commit=False)
                structure.user = request.user
                structure.save()

            formset = StructureComponentFormSet(request.POST, instance=structure, user=request.user, prefix=prefix)

            if formset.is_valid():
                formset.save()
                return redirect('main:prix_indexes')
        else:
            print("❌ Formulaire principal invalide")
            print(form.errors)
            formset = StructureComponentFormSet(request.POST, instance=structure, user=request.user, prefix=prefix)

    else:
        print("🔄 Requête GET")
        structure = IndexedPriceStructure(user=request.user)
        form = IndexedPriceStructureForm()
        formset = StructureComponentFormSet(user=request.user, instance=structure, prefix=prefix)

    # Important pour l’ajout dynamique
    formset.empty_form.user = request.user
    formset.empty_form.fields['index'].queryset = request.user.userprofile.favorite_indexes.all()

    structures = IndexedPriceStructure.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'prix_indexes.html', {
        'form': form,
        'formset': formset,
        'structures': structures,
    })



@require_POST
@login_required
def delete_structure(request, pk):
    structure = get_object_or_404(IndexedPriceStructure, pk=pk, user=request.user)
    structure.delete()
    return redirect('main:prix_indexes')


@login_required
def get_structure_data(request, structure_id):
    structure = get_object_or_404(IndexedPriceStructure, id=structure_id, user=request.user)

    data = {
        "id": structure.id,
        "name": structure.name,
        "base_price": float(structure.base_price),
        "reference_date": structure.reference_date.strftime("%Y-%m-%d"),
        "components": [],
    }

    for comp in structure.components.all():
        data["components"].append({
            "label": comp.label,
            "component_type": comp.component_type,
            "percentage": float(comp.percentage) if comp.percentage else "",
            "fixed_amount": float(comp.fixed_amount) if comp.fixed_amount else "",
            "index_id": comp.index.id if comp.index else None,
        })

    return JsonResponse(data)
