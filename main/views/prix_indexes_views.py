from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from main.models import Product, Part, IndexValue
from main.forms import ProductForm, PartFormSet
from main.utils import get_user_index_data
import json
from django.db.models import Avg, Q
from datetime import datetime


@login_required
def prix_indexes_view(request):
    prefix = "components"

    if request.method == "POST":
        structure_id = request.POST.get("structure_id")
        structure = None

        if structure_id:
            try:
                structure = Product.objects.get(id=structure_id,
                                                user=request.user)
                form = ProductForm(request.POST, instance=structure)
            except Product.DoesNotExist:
                structure = Product(user=request.user)
                form = ProductForm(request.POST)
        else:
            structure = Product(user=request.user)
            form = ProductForm(request.POST)

        if form.is_valid():
            if structure_id:
                structure = form.save()
                structure.parts.all().delete()

            else:
                structure = form.save(commit=False)
                structure.user = request.user
                structure.save()

            formset = PartFormSet(request.POST,
                                  instance=structure,
                                  user=request.user,
                                  prefix=prefix)

            if formset.is_valid():
                formset.save()
                return redirect('main:prix_indexes')
        else:
            formset = PartFormSet(request.POST,
                                  instance=structure,
                                  user=request.user,
                                  prefix=prefix)
    else:
        structure = Product(user=request.user)
        form = ProductForm()
        formset = PartFormSet(user=request.user,
                              instance=structure,
                              prefix=prefix)

    structures = Product.objects.filter(
        user=request.user).order_by('-created_at')

    # Graph data
    structure_graphs = {}
    structures_meta = {}
    index_data = get_user_index_data(request.user)

    for s in structures:
        data_points = []
        parts = s.parts.all()  # ✅ on remplace "components" par "parts"

        # Graph generation
        index_ids = [
            p.index_id for p in parts
            if p.component_type == "indexed" and p.index_id
        ]
        all_dates = sorted(set().union(*(index_data.get(i, {}).keys()
                                         for i in index_ids)))

        for date in all_dates:
            total = 0
            for part in parts:
                if part.component_type == 'indexed' and part.index_id and part.percentage:
                    series = index_data.get(part.index_id, {})
                    ref_date = part.reference_date
                    base_val = series.get(ref_date)
                    current_val = series.get(date)
                    if base_val and current_val:
                        montant = part.percentage / 100 * current_val / base_val
                        total += montant
            data_points.append({
                "date": date.strftime("%Y-%m"),
                "value": round(total, 2)
            })




        
        structure_graphs[s.id] = data_points

        # Meta structure data
        structures_meta[s.id] = {
            "name":
            s.name,
            "components": [{
                "label": p.label,
                "component_type": p.component_type,
                "fixed_amount": float(p.fixed_amount) if p.fixed_amount else None,
                "percentage": float(p.percentage) if p.percentage else None,
                "index_name": p.index.name if p.index else None,
            } for p in parts]

        }
    produits = Product.objects.filter(
    user=request.user).prefetch_related("parts")


    context = {
        "form": form,
        "formset": formset,
        "structures": structures,
        "structure_graphs_json": json.dumps(structure_graphs),
        "structures_meta_json": json.dumps(structures_meta),
        "produits": produits,  # ✅ Ajout essentiel
    }

    return render(request, "prix_indexes.html", context)


@require_POST
@login_required
def delete_structure(request, pk):
    structure = get_object_or_404(Product, pk=pk, user=request.user)
    structure.delete()
    return redirect('main:prix_indexes')


@login_required
def get_structure_data(request, pk):
    structure = get_object_or_404(Product, pk=pk, user=request.user)

    data = {
        "name":
        structure.name,
        "components": [{
            "label": p.label,
            "component_type": p.component_type,
            "fixed_amount": float(p.fixed_amount) if p.fixed_amount else None,
            "percentage": float(p.percentage) if p.percentage else None,
            "index_id": p.index.id if p.index else None,
        } for p in structure.parts.all()]

    }

    return JsonResponse(data)
