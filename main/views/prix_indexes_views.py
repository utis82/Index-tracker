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
                structure = Product.objects.get(id=structure_id, user=request.user)
                form = ProductForm(request.POST, instance=structure)
            except Product.DoesNotExist:
                structure = Product(user=request.user)
                form = ProductForm(request.POST)
        else:
            structure = Product(user=request.user)
            form = ProductForm(request.POST)

        if form.is_valid():
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
            slice.index_id
            for part in parts
            for slice in part.slices.all()
            if slice.component_type == "indexed" and slice.index_id
        ]


        all_dates = sorted(set().union(*(index_data.get(i, {}).keys()
                                         for i in index_ids)))

        for date in all_dates:
            total = 0
            for part in parts:
                for slice in part.slices.all():
                    if slice.component_type == 'indexed' and slice.index_id and slice.percentage:
                        series = index_data.get(slice.index_id, {})
                        ref_date = part.reference_date
                        base_val = series.get(ref_date)
                        current_val = series.get(date)
                        if base_val and current_val:
                            montant = slice.percentage / 100 * current_val / base_val
                            total += montant

            data_points.append({
                "date": date.strftime("%Y-%m"),
                "value": round(total, 2)
            })




        
        structure_graphs[s.id] = data_points

        # Meta structure data
        structures_meta[s.id] = {
            "name": s.name,
            "components": [
                {
                    "label": slice.label,
                    "component_type": slice.component_type,
                    "fixed_amount": float(slice.fixed_amount) if slice.fixed_amount else None,
                    "percentage": float(slice.percentage) if slice.percentage else None,
                    "index_name": slice.index.name if slice.index else None,
                }
                for part in s.parts.all()
                for slice in part.slices.all()
            ]
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
    return JsonResponse({"status": "ok"})


@require_POST
@login_required
def get_structure_data(request, pk):
    structure = get_object_or_404(Product, pk=pk, user=request.user)

    components = []
    for part in structure.parts.all():
        for slice in part.slices.all():
            components.append({
                "label": slice.label,
                "component_type": slice.component_type,
                "fixed_amount": float(slice.fixed_amount) if slice.fixed_amount else None,
                "percentage": float(slice.percentage) if slice.percentage else None,
                "index_id": slice.index.id if slice.index else None,
            })

    data = {
        "name": structure.name,
        "components": components
    }

    return JsonResponse(data)


@require_POST
@login_required
def create_part(request):
    name = request.POST.get("name")
    reference_date = request.POST.get("reference_date")
    reference_date = datetime.strptime(reference_date, "%Y-%m-%d").date() if reference_date else None
    product_id = request.POST.get("product_id")

    product = get_object_or_404(Product, id=product_id, user=request.user)

    Part.objects.create(
        name=name,
        reference_date=reference_date,
        product=product
    )

    return redirect("main:prix_indexes")
