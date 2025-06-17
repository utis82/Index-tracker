from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from main.models import Product, Part, IndexValue, Slice, Index
from main.forms import ProductForm, PartFormSet, PartForm
from main.utils import get_user_index_data
import json
from datetime import datetime
from datetime import date as datetime_date


@login_required
def prix_indexes_view(request):
    prefix = "components"

    if request.method == "POST":
        # 🚨 Suppression d'une pièce
        if request.POST.get("delete_part"):
            part_id = request.POST.get("part_id")
            if part_id:
                try:
                    part = Part.objects.get(id=part_id, product__user=request.user)
                    part.delete()
                    return JsonResponse({"status": "success"})
                except Part.DoesNotExist:
                    return JsonResponse({"status": "error", "message": "Pièce non trouvée"})
            return redirect('main:prix_indexes')

        # 🚨 Suppression d'un produit
        if request.POST.get("delete_product"):
            product_id = request.POST.get("product_id")
            if product_id:
                try:
                    product = Product.objects.get(id=product_id, user=request.user)
                    product.delete()
                    return JsonResponse({"status": "success"})
                except Product.DoesNotExist:
                    return JsonResponse({"status": "error", "message": "Produit non trouvé"})
            return redirect('main:prix_indexes')

        # === Gestion des Parts (pièces) avec tranches ===
        part_id = request.POST.get("part_id")
        if request.POST.get("name") and request.POST.get("reference_date") and request.POST.get("product_id"):
            # ✅ C'est une pièce - on valide les tranches
            slice_data = extract_slice_data(request.POST)
            validation_error = validate_slices(slice_data)

            if validation_error:
                return JsonResponse({"status": "error", "message": validation_error})

            # Validation du prix de référence
            try:
                reference_price = float(request.POST.get("reference_price", 0))
                if reference_price <= 0:
                    return JsonResponse({"status": "error", "message": "Le prix de référence doit être supérieur à 0"})
            except (ValueError, TypeError):
                return JsonResponse({"status": "error", "message": "Prix de référence invalide"})

            if part_id:
                # Modification d'une pièce existante
                try:
                    selected_part = Part.objects.get(id=part_id, product__user=request.user)
                    part_form = PartForm(request.POST, instance=selected_part)
                    if part_form.is_valid():
                        part = part_form.save(commit=False)
                        part.reference_price = reference_price
                        product_id = request.POST.get("product_id")
                        if product_id:
                            try:
                                product = Product.objects.get(id=product_id, user=request.user)
                                part.product = product
                                part.save()

                                # Supprimer les anciennes tranches et créer les nouvelles
                                part.slices.all().delete()
                                create_slices_for_part(part, slice_data, request.user)

                                return JsonResponse({"status": "success"})
                            except Product.DoesNotExist:
                                return JsonResponse({"status": "error", "message": "Produit non trouvé"})
                except Part.DoesNotExist:
                    return JsonResponse({"status": "error", "message": "Pièce non trouvée"})
            else:
                # Création d'une nouvelle pièce
                part_form = PartForm(request.POST)
                if part_form.is_valid():
                    part = part_form.save(commit=False)
                    part.reference_price = reference_price
                    product_id = request.POST.get("product_id")
                    if product_id:
                        try:
                            product = Product.objects.get(id=product_id, user=request.user)
                            part.product = product
                            part.save()

                            # Créer les tranches
                            create_slices_for_part(part, slice_data, request.user)

                            return JsonResponse({"status": "success"})
                        except Product.DoesNotExist:
                            return JsonResponse({"status": "error", "message": "Produit non trouvé"})

        # === Gestion des Products (structures) ===
        elif request.POST.get("name") and not request.POST.get("product_id"):
            # ✅ C'est un produit - PAS de validation des tranches
            structure_id = request.POST.get("structure_id")
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
                return redirect('main:prix_indexes')
            else:
                return JsonResponse({"status": "error", "message": "Formulaire invalide"})

        return JsonResponse({"status": "error", "message": "Données manquantes"})

    # === Gestion GET ===
    structure = Product(user=request.user)
    form = ProductForm()
    formset = PartFormSet(user=request.user, instance=structure, prefix=prefix)
    part_form = PartForm()

    # === Récupération des données pour affichage ===
    structures = Product.objects.filter(user=request.user).order_by('-created_at')
    structure_graphs = {}
    part_graphs = {}
    structures_meta = {}

    try:
        index_data = get_user_index_data(request.user)
    except:
        index_data = {}

    # Calcul des graphiques PRODUITS avec prix réels
    for s in structures:
        data_points = []
        parts = s.parts.all()

        # 🔥 CORRECTION : Vérifier qu'il y a des pièces avec des tranches
        all_slices = []
        for part in parts:
            all_slices.extend(part.slices.all())

        if not all_slices:
            # Pas de tranches, pas de graphique
            structure_graphs[s.id] = []
            continue

        # Récupérer tous les index utilisés dans ce produit
        index_ids = [
            sl.index_id
            for part in parts
            for sl in part.slices.all()
            if sl.component_type == "indexed" and sl.index_id
        ]

        # Vérifier s'il y a des tranches fixes
        has_fixed_slices = any(
            sl.component_type == "fixed" 
            for part in parts 
            for sl in part.slices.all()
        )

        if index_ids:  # Il y a des tranches indexées
            all_dates = sorted(set().union(*(index_data.get(i, {}).keys() for i in index_ids)))
            product_reference_date = s.reference_date

            for date in all_dates:
                if date >= product_reference_date:
                    total_price = 0

                    # Calculer le prix de chaque pièce
                    for part in parts:
                        part_current_price = calculate_part_price_at_date(part, date, index_data)
                        total_price += part_current_price

                    data_points.append({
                        "date": date.strftime("%Y-%m") if hasattr(date, 'strftime') else str(date),
                        "value": round(total_price, 2)
                    })
        elif has_fixed_slices:  # 🆕 Seulement des tranches fixes
            # Créer une ligne horizontale de la date de référence à aujourd'hui
            total_price = 0
            for part in parts:
                part_current_price = calculate_part_price_at_date(part, s.reference_date, index_data)
                total_price += part_current_price

            # Créer des points mensuels de la référence à aujourd'hui
            ref_date = s.reference_date
            today = datetime_date.today()

            current_date = datetime_date(ref_date.year, ref_date.month, 1)  # Premier du mois de référence

            while current_date <= today:
                data_points.append({
                    "date": current_date.strftime("%Y-%m"),
                    "value": round(total_price, 2)
                })

                # Passer au mois suivant
                if current_date.month == 12:
                    current_date = datetime_date(current_date.year + 1, 1, 1)
                else:
                    current_date = datetime_date(current_date.year, current_date.month + 1, 1)

        structure_graphs[s.id] = data_points

    # ✨ Calcul des graphiques PIÈCES avec prix réels
    for s in structures:
        for part in s.parts.all():
            part_data_points = []

            # Vérifier qu'il y a des tranches
            if not part.slices.exists():
                part_graphs[part.id] = []
                continue

            # Récupérer tous les index utilisés dans cette pièce
            part_index_ids = [
                sl.index_id
                for sl in part.slices.all()
                if sl.component_type == "indexed" and sl.index_id
            ]

            # Vérifier s'il y a des tranches fixes
            has_fixed_slices = any(
                sl.component_type == "fixed" 
                for sl in part.slices.all()
            )

            if part_index_ids:  # La pièce a des tranches indexées
                all_dates = sorted(set().union(*(index_data.get(i, {}).keys() for i in part_index_ids)))
                part_reference_date = part.reference_date

                for date in all_dates:
                    if date >= part_reference_date:
                        part_current_price = calculate_part_price_at_date(part, date, index_data)

                        part_data_points.append({
                            "date": date.strftime("%Y-%m") if hasattr(date, 'strftime') else str(date),
                            "value": round(part_current_price, 2)
                        })
            elif has_fixed_slices:  # 🆕 Seulement des tranches fixes
                # Créer une ligne horizontale de la date de référence à aujourd'hui
                part_current_price = calculate_part_price_at_date(part, part.reference_date, index_data)

                # Créer des points mensuels de la référence à aujourd'hui
                ref_date = part.reference_date
                today = datetime_date.today()

                current_date = datetime_date(ref_date.year, ref_date.month, 1)  # Premier du mois de référence

                while current_date <= today:
                    part_data_points.append({
                        "date": current_date.strftime("%Y-%m"),
                        "value": round(part_current_price, 2)
                    })

                    # Passer au mois suivant
                    if current_date.month == 12:
                        current_date = datetime_date(current_date.year + 1, 1, 1)
                    else:
                        current_date = datetime_date(current_date.year, current_date.month + 1, 1)

            part_graphs[part.id] = part_data_points

    # Meta données avec prix de référence
    for s in structures:
        structures_meta[s.id] = {
            "name": s.name,
            "reference_price": s.total_reference_price(),
            "components": [
                {
                    "label": sl.label,
                    "component_type": sl.component_type,
                    "fixed_amount": float(sl.fixed_amount) if sl.fixed_amount else None,
                    "percentage": float(sl.percentage) if sl.percentage else None,
                    "index_name": sl.index.name if sl.index else None,
                    "part_reference_price": float(sl.part.reference_price),
                }
                for part in s.parts.all()
                for sl in part.slices.all()
            ]
        }

    produits = Product.objects.filter(user=request.user).prefetch_related("parts__slices")

    # Récupérer les index favoris pour le modal
    favorite_indexes = []
    if hasattr(request.user, 'userprofile'):
        favorite_indexes = request.user.userprofile.favorite_indexes.all()

    # Calculer les prix actuels pour l'affichage
    current_prices = get_current_prices_for_display(request.user)

    context = {
        "form": form,
        "formset": formset,
        "structures": structures,
        "structure_graphs_json": json.dumps(structure_graphs),
        "part_graphs_json": json.dumps(part_graphs),
        "structures_meta_json": json.dumps(structures_meta),
        "produits": produits,
        "part_form": part_form,
        "favorite_indexes": favorite_indexes,
        "favorite_indexes_json": json.dumps([
            {"id": idx.id, "name": idx.name, "unit": idx.unit} 
            for idx in favorite_indexes
        ]),
        "current_prices": current_prices,  # ✨ NOUVEAU
    }

    return render(request, "prix_indexes.html", context)


def calculate_part_price_at_date(part, target_date, index_data):
    """Calcule le prix d'une pièce à une date donnée"""
    total_price = 0  # 🔥 CORRECTION : partir de 0 au lieu du prix de référence

    for slice_obj in part.slices.all():
        slice_reference_value = part.reference_price * (slice_obj.percentage / 100)

        if slice_obj.component_type == 'indexed' and slice_obj.index_id and slice_obj.percentage:
            # Calcul pour tranches indexées
            series = index_data.get(slice_obj.index_id, {})
            base_val = series.get(part.reference_date)
            current_val = series.get(target_date)

            if base_val and current_val and base_val != 0:
                evolution_ratio = current_val / base_val
                slice_current_value = slice_reference_value * evolution_ratio
                total_price += slice_current_value
            else:
                # Pas de données d'index, utiliser la valeur de référence
                total_price += slice_reference_value

        elif slice_obj.component_type == 'fixed' and slice_obj.percentage:
            # 🆕 Calcul pour tranches fixes - reste constant
            total_price += slice_reference_value

    return total_price


def extract_slice_data(post_data):
    """Extrait les données des tranches depuis POST"""
    slice_data = []
    i = 0
    while f"slice_label_{i}" in post_data:
        label = post_data.get(f"slice_label_{i}", "").strip()
        component_type = post_data.get(f"slice_type_{i}", "")
        index_id = post_data.get(f"slice_index_{i}", "")
        percentage = post_data.get(f"slice_percentage_{i}", "")

        if label and component_type and percentage:
            slice_info = {
                "label": label,
                "component_type": component_type,
                "percentage": float(percentage),
                "index_id": int(index_id) if index_id and index_id != "" else None
            }
            slice_data.append(slice_info)
        i += 1
    return slice_data


def validate_slices(slice_data):
    """Valide que les tranches font bien 100%"""
    if not slice_data:
        return "Au moins une tranche est requise"

    total_percentage = sum(slice["percentage"] for slice in slice_data)
    if abs(total_percentage - 100) > 0.1:
        return f"La somme des pourcentages doit être égale à 100% (actuellement {total_percentage}%)"

    # Vérifier que les tranches indexées ont bien un index
    for slice_info in slice_data:
        if slice_info["component_type"] == "indexed" and not slice_info["index_id"]:
            return f"La tranche '{slice_info['label']}' de type 'Indexé' doit avoir un index sélectionné"

    return None


def create_slices_for_part(part, slice_data, user):
    """Crée les tranches pour une pièce"""
    for slice_info in slice_data:
        slice_obj = Slice(
            part=part,
            label=slice_info["label"],
            component_type=slice_info["component_type"],
            percentage=slice_info["percentage"],
            reference_date=part.reference_date
        )

        if slice_info["component_type"] == "indexed" and slice_info["index_id"]:
            try:
                # Vérifier que l'index est dans les favoris de l'utilisateur
                index = user.userprofile.favorite_indexes.get(id=slice_info["index_id"])
                slice_obj.index = index
            except Index.DoesNotExist:
                pass  # Ignorer si l'index n'est pas trouvé

        slice_obj.save()


@require_POST
@login_required
def get_part_data(request, part_id):
    """Récupère les données d'une pièce avec ses tranches pour l'édition"""
    try:
        part = Part.objects.get(id=part_id, product__user=request.user)
        slices_data = []

        for slice_obj in part.slices.all():
            slices_data.append({
                "label": slice_obj.label,
                "component_type": slice_obj.component_type,
                "percentage": float(slice_obj.percentage) if slice_obj.percentage else 0,
                "index_id": slice_obj.index.id if slice_obj.index else None,
                "index_name": slice_obj.index.name if slice_obj.index else None,
            })

        data = {
            "name": part.name,
            "reference_date": part.reference_date.strftime("%Y-%m-%d"),
            "reference_price": float(part.reference_price),
            "product_id": part.product.id,
            "slices": slices_data
        }

        return JsonResponse({"status": "success", "data": data})
    except Part.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Pièce non trouvée"})


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
                "part_reference_price": float(slice.part.reference_price),
            })

    data = {
        "name": structure.name,
        "reference_price": structure.total_reference_price(),
        "components": components
    }

    return JsonResponse(data)


def get_current_prices_for_display(user):
    """Calcule les prix actuels pour l'affichage dans l'arborescence"""
    try:
        index_data = get_user_index_data(user)
    except:
        index_data = {}

    today = datetime_date.today()
    prices_data = {}

    # Calculer pour tous les produits et leurs pièces
    products = Product.objects.filter(user=user).prefetch_related("parts__slices__index")

    for product in products:
        product_current_total = 0
        product_reference_total = product.total_reference_price()

        # Calculer pour chaque pièce
        parts_prices = {}
        for part in product.parts.all():
            part_reference_price = part.reference_price

            # Trouver la date la plus récente disponible dans les index
            part_index_ids = [
                sl.index_id for sl in part.slices.all() 
                if sl.component_type == "indexed" and sl.index_id
            ]

            if part_index_ids:
                # Chercher la date la plus récente avec des données
                available_dates = set()
                for index_id in part_index_ids:
                    if index_id in index_data:
                        available_dates.update(index_data[index_id].keys())

                if available_dates:
                    # Prendre la date la plus récente (pas forcément aujourd'hui)
                    latest_date = max(available_dates)
                    part_current_price = calculate_part_price_at_date(part, latest_date, index_data)
                else:
                    part_current_price = part_reference_price
            else:
                # Pas d'index, le prix reste identique
                part_current_price = part_reference_price

            parts_prices[part.id] = {
                'reference': part_reference_price,
                'current': part_current_price
            }
            product_current_total += part_current_price

        prices_data[product.id] = {
            'reference': product_reference_total,
            'current': product_current_total,
            'parts': parts_prices
        }

    return prices_data