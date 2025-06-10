from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from main.models import IndexedPriceStructure,StructureComponent, IndexValue
from main.forms import IndexedPriceStructureForm, StructureComponentFormSet
from main.utils import get_user_index_data
import json
from django.db.models import Avg,Q
from datetime import datetime

@login_required
def prix_indexes_view(request):
    prefix = "components"

    if request.method == "POST":
        structure_id = request.POST.get("structure_id")
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
            formset = StructureComponentFormSet(request.POST, instance=structure, user=request.user, prefix=prefix)
    else:
        structure = IndexedPriceStructure(user=request.user)
        form = IndexedPriceStructureForm()
        formset = StructureComponentFormSet(user=request.user, instance=structure, prefix=prefix)

    formset.empty_form.user = request.user
    formset.empty_form.fields['index'].queryset = request.user.userprofile.favorite_indexes.all()

    structures = IndexedPriceStructure.objects.filter(user=request.user).order_by('-created_at')

    # Graph data
    structure_graphs = {}
    structures_meta = {}
    index_data = get_user_index_data(request.user)

    for s in structures:
        data_points = []
        base_price = s.base_price
        ref_date = s.reference_date
        components = s.components.all()

        # Graph generation
        index_ids = [c.index_id for c in components if c.component_type == "indexed" and c.index_id]
        all_dates = sorted(set().union(*(index_data.get(i, {}).keys() for i in index_ids)))

        for date in all_dates:
            total = base_price
            for comp in components:
                if comp.component_type == 'indexed' and comp.index_id and comp.percentage:
                    series = index_data.get(comp.index_id, {})
                    base_val = series.get(ref_date)
                    current_val = series.get(date)
                    if base_val and current_val:
                        montant = base_price * comp.percentage / 100 * current_val / base_val
                        total += montant
            data_points.append({
                "date": date.strftime("%Y-%m"),
                "value": round(total, 2)
            })
        structure_graphs[s.id] = data_points

        # Meta structure data
        structures_meta[s.id] = {
            "name": s.name,
            "reference_date": s.reference_date.strftime("%Y-%m-%d"),
            "base_price": float(s.base_price),
            "components": [
                {
                    "label": c.label,
                    "component_type": c.component_type,
                    "fixed_amount": float(c.fixed_amount) if c.fixed_amount else None,
                    "percentage": float(c.percentage) if c.percentage else None,
                    "index_name": c.index.name if c.index else None,
                }
                for c in components
            ]
        }

    context = {
        "form": form,
        "formset": formset,
        "structures": structures,
        "structure_graphs_json": json.dumps(structure_graphs),
        "structures_meta_json": json.dumps(structures_meta),
    }

    return render(request, "prix_indexes.html", context)


@require_POST
@login_required
def delete_structure(request, pk):
    structure = get_object_or_404(IndexedPriceStructure, pk=pk, user=request.user)
    structure.delete()
    return redirect('main:prix_indexes')

@login_required
def get_structure_data(request, pk):
    structure = get_object_or_404(IndexedPriceStructure, pk=pk, user=request.user)

    data = {
        "name": structure.name,
        "base_price": float(structure.base_price),
        "reference_date": structure.reference_date.strftime("%Y-%m-%d"),
        "components": [
            {
                "label": c.label,
                "component_type": c.component_type,
                "fixed_amount": float(c.fixed_amount) if c.fixed_amount else None,
                "percentage": float(c.percentage) if c.percentage else None,
                "index_id": c.index.id if c.index else None,
            }
            for c in structure.components.all()
        ]
    }

    return JsonResponse(data)