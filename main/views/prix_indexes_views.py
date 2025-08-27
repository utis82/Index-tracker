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
                    part = Part.objects.get(id=part_id, user=request.user)
                    part.delete()
                    return JsonResponse({"status": "success"})
                except Part.DoesNotExist:
                    return JsonResponse({
                        "status": "error",
                        "message": "Pièce non trouvée"
                    })
            return redirect('main:prix_indexes')

        # 🚨 Suppression d'un produit
        if request.POST.get("delete_product"):
            product_id = request.POST.get("product_id")
            if product_id:
                try:
                    product = Product.objects.get(id=product_id,
                                                  user=request.user)
                    product.delete()
                    return JsonResponse({"status": "success"})
                except Product.DoesNotExist:
                    return JsonResponse({
                        "status": "error",
                        "message": "Produit non trouvé"
                    })
            return redirect('main:prix_indexes')

        # === LOGIQUE CLAIRE : Différencier Product vs Part ===

        # Dans votre vue prix_indexes_view, modifiez la section de gestion des PARTS

        # ✅ GESTION DES PARTS (ont reference_price dans le POST)
        if request.POST.get("reference_price"):
            part_id = request.POST.get("part_id")

            # Extraire les données des tranches AVANT la validation
            slice_data = extract_slice_data_v2(request.POST)
            validation_error = validate_slices(slice_data)
            if validation_error:
                return JsonResponse({
                    "status": "error",
                    "message": validation_error
                })

            try:
                reference_price = float(request.POST.get("reference_price", 0))
                if reference_price <= 0:
                    return JsonResponse({
                        "status":
                        "error",
                        "message":
                        "Le prix de référence doit être supérieur à 0"
                    })
            except (ValueError, TypeError):
                return JsonResponse({
                    "status": "error",
                    "message": "Prix de référence invalide"
                })

            if part_id:
                # Modification d'une pièce existante
                try:
                    selected_part = Part.objects.get(id=part_id,
                                                     user=request.user)
                    part_form = PartForm(request.POST, instance=selected_part)
                    if part_form.is_valid():
                        part = part_form.save(commit=False)
                        part.reference_price = reference_price
                        part.user = request.user

                        # 🔧 AJOUT : Récupération manuelle du part_number
                        part.part_number = request.POST.get("part_number", "")

                        # Gestion du product_id (optionnel maintenant)
                        product_id = request.POST.get("product_id")
                        if product_id and product_id != "":
                            try:
                                product = Product.objects.get(
                                    id=product_id, user=request.user)
                                part.product = product
                            except Product.DoesNotExist:
                                return JsonResponse({
                                    "status":
                                    "error",
                                    "message":
                                    "Produit non trouvé"
                                })
                        else:
                            part.product = None  # Part orpheline

                        part.save()

                        # Supprimer les anciennes tranches et créer les nouvelles
                        part.slices.all().delete()
                        create_slices_for_part_v2(part, slice_data,
                                                  request.user)

                        return JsonResponse({"status": "success"})
                    else:
                        return JsonResponse({
                            "status": "error",
                            "message": "Formulaire invalide"
                        })
                except Part.DoesNotExist:
                    return JsonResponse({
                        "status": "error",
                        "message": "Pièce non trouvée"
                    })
            else:
                # Création d'une nouvelle pièce
                part_form = PartForm(request.POST)
                if part_form.is_valid():
                    part = part_form.save(commit=False)
                    part.reference_price = reference_price
                    part.user = request.user

                    # 🔧 AJOUT : Récupération manuelle du part_number
                    part.part_number = request.POST.get("part_number", "")

                    # Gestion du product_id (optionnel maintenant)
                    product_id = request.POST.get("product_id")
                    if product_id and product_id != "":
                        try:
                            product = Product.objects.get(id=product_id,
                                                          user=request.user)
                            part.product = product
                        except Product.DoesNotExist:
                            return JsonResponse({
                                "status": "error",
                                "message": "Produit non trouvé"
                            })
                    else:
                        part.product = None  # Part orpheline

                    part.save()

                    # Créer les tranches
                    create_slices_for_part_v2(part, slice_data, request.user)

                    return JsonResponse({"status": "success"})
                else:
                    return JsonResponse({
                        "status": "error",
                        "message": "Formulaire part invalide"
                    })


        # ✅ GESTION DES PRODUCTS (n'ont PAS reference_price dans le POST)
        elif request.POST.get("name") and request.POST.get("reference_date"):
            structure_id = request.POST.get("structure_id")

            if structure_id:
                # Modification d'un produit existant
                try:
                    structure = Product.objects.get(id=structure_id, user=request.user)
                    form = ProductForm(request.POST, instance=structure)
                except Product.DoesNotExist:
                    structure = Product(user=request.user)
                    form = ProductForm(request.POST)
            else:
                # Création d'un nouveau produit
                structure = Product(user=request.user)
                form = ProductForm(request.POST)

            if form.is_valid():
                structure = form.save(commit=False)
                structure.user = request.user

                # 🔧 AJOUT : Récupération manuelle du part_number (au cas où)
                # Normalement le formulaire devrait le gérer, mais par sécurité
                if 'part_number' in request.POST:
                    structure.part_number = request.POST.get("part_number", "")

                structure.save()
                return redirect('main:prix_indexes')
            else:
                return JsonResponse({
                    "status": "error",
                    "message": "Formulaire product invalide"
                })

        # Si aucune condition n'est remplie
        return JsonResponse({
            "status": "error",
            "message": "Données manquantes ou invalides"
        })

    # === Gestion GET ===
    structure = Product(user=request.user)
    form = ProductForm()
    formset = PartFormSet(user=request.user, instance=structure, prefix=prefix)
    part_form = PartForm()

    # === Récupération des données pour affichage ===
    structures = Product.objects.filter(user=request.user).order_by('-id')
    orphan_parts = Part.objects.filter(user=request.user,
                                       product__isnull=True).order_by('-id')
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

        # Vérifier qu'il y a des pièces avec des tranches
        all_slices = []
        for part in parts:
            all_slices.extend(part.slices.all())

        if not all_slices:
            # Pas de tranches, pas de graphique
            structure_graphs[s.id] = []
            continue

        # Récupérer tous les index utilisés dans ce produit
        index_ids = [
            sl.index_id for part in parts for sl in part.slices.all()
            if sl.component_type == "indexed" and sl.index_id
        ]

        # Vérifier s'il y a des tranches fixes
        has_fixed_slices = any(sl.component_type == "fixed" for part in parts
                               for sl in part.slices.all())

        if index_ids:  # Il y a des tranches indexées
            all_dates = sorted(set().union(*(index_data.get(i, {}).keys()
                                             for i in index_ids)))
            product_reference_date = s.reference_date

            for date in all_dates:
                if date >= product_reference_date:
                    total_price = 0

                    # Calculer le prix de chaque pièce
                    for part in parts:
                        part_current_price = calculate_part_price_at_date_v3(
                            part, date, index_data)
                        total_price += part_current_price

                    data_points.append({
                        "date":
                        date.strftime("%Y-%m")
                        if hasattr(date, 'strftime') else str(date),
                        "value":
                        round(total_price, 2)
                    })
        elif has_fixed_slices:  # Seulement des tranches fixes
            # Créer une ligne horizontale de la date de référence à aujourd'hui
            total_price = 0
            for part in parts:
                part_current_price = calculate_part_price_at_date_v3(
                    part, s.reference_date, index_data)
                total_price += part_current_price

            # Créer des points mensuels de la référence à aujourd'hui
            ref_date = s.reference_date
            today = datetime_date.today()

            current_date = datetime_date(ref_date.year, ref_date.month, 1)

            while current_date <= today:
                data_points.append({
                    "date": current_date.strftime("%Y-%m"),
                    "value": round(total_price, 2)
                })

                # Passer au mois suivant
                if current_date.month == 12:
                    current_date = datetime_date(current_date.year + 1, 1, 1)
                else:
                    current_date = datetime_date(current_date.year,
                                                 current_date.month + 1, 1)

        structure_graphs[s.id] = data_points

    # Calcul des graphiques PIÈCES (produits + orphelines)
    all_parts = []
    # Ajouter les parts des produits
    for s in structures:
        all_parts.extend(s.parts.all())
    # Ajouter les parts orphelines
    all_parts.extend(orphan_parts)

    for part in all_parts:
        part_data_points = []

        # Vérifier qu'il y a des tranches
        if not part.slices.exists():
            part_graphs[part.id] = []
            continue

        # Récupérer tous les index utilisés dans cette pièce
        part_index_ids = [
            sl.index_id for sl in part.slices.all()
            if sl.component_type == "indexed" and sl.index_id
        ]

        # Vérifier s'il y a des tranches fixes
        has_fixed_slices = any(sl.component_type == "fixed"
                               for sl in part.slices.all())

        if part_index_ids:  # La pièce a des tranches indexées
            all_dates = sorted(set().union(*(index_data.get(i, {}).keys()
                                             for i in part_index_ids)))
            part_reference_date = part.reference_date

            for date in all_dates:
                if date >= part_reference_date:
                    part_current_price = calculate_part_price_at_date_v3(
                        part, date, index_data)

                    part_data_points.append({
                        "date":
                        date.strftime("%Y-%m")
                        if hasattr(date, 'strftime') else str(date),
                        "value":
                        round(part_current_price, 2)
                    })
        elif has_fixed_slices:  # Seulement des tranches fixes
            # Créer une ligne horizontale de la date de référence à aujourd'hui
            part_current_price = calculate_part_price_at_date_v3(
                part, part.reference_date, index_data)

            # Créer des points mensuels de la référence à aujourd'hui
            ref_date = part.reference_date
            today = datetime_date.today()

            current_date = datetime_date(ref_date.year, ref_date.month, 1)

            while current_date <= today:
                part_data_points.append({
                    "date": current_date.strftime("%Y-%m"),
                    "value": round(part_current_price, 2)
                })

                # Passer au mois suivant
                if current_date.month == 12:
                    current_date = datetime_date(current_date.year + 1, 1, 1)
                else:
                    current_date = datetime_date(current_date.year,
                                                 current_date.month + 1, 1)

        part_graphs[part.id] = part_data_points

    # Meta données avec prix de référence
    for s in structures:
        structures_meta[s.id] = {
            "name":
            s.name,
            "reference_price":
            s.total_reference_price(),
            "components": [{
                "label":
                sl.label,
                "component_type":
                sl.component_type,
                "fixed_amount":
                float(sl.fixed_amount) if sl.fixed_amount else None,
                "percentage":
                float(sl.percentage) if sl.percentage else None,
                "index_name":
                sl.index.name if sl.index else None,
                "part_reference_price":
                float(sl.part.reference_price),
            } for part in s.parts.all() for sl in part.slices.all()]
        }

    produits = Product.objects.filter(
        user=request.user).prefetch_related("parts__slices")

    # Récupérer les index favoris pour le modal
    favorite_indexes = []
    if hasattr(request.user, 'userprofile'):
        favorite_indexes = request.user.userprofile.favorite_indexes.all()

    # Calculer les prix actuels pour l'affichage
    current_prices = get_current_prices_for_display(request.user)

    context = {
        "form":
        form,
        "formset":
        formset,
        "structures":
        structures,
        "orphan_parts":
        orphan_parts,
        "structure_graphs_json":
        json.dumps(structure_graphs),
        "part_graphs_json":
        json.dumps(part_graphs),
        "structures_meta_json":
        json.dumps(structures_meta),
        "produits":
        produits,
        "part_form":
        part_form,
        "favorite_indexes":
        favorite_indexes,
        "favorite_indexes_json":
        json.dumps([{
            "id": idx.id,
            "name": idx.name,
            "unit": idx.unit
        } for idx in favorite_indexes]),
        "current_prices":
        current_prices,
    }

    return render(request, "prix_indexes.html", context)


def calculate_reference_price_for_fixed_criteria(slice_data, user,
                                                 reference_date):
    """Calcule le prix de référence pour une part en mode Fixed Criteria"""
    total_reference_price = 0

    try:
        index_data = get_user_index_data(user)
    except:
        return 1.0  # Fallback si pas de données d'index

    for slice_info in slice_data:
        if slice_info["mode"] == "fixed_criteria":
            criteria_value = slice_info["criteria_value_tonnes"]
            index_id = slice_info["index_id"]

            # Récupérer la valeur de l'index à la date de référence
            if index_id in index_data:
                index_series = index_data[index_id]
                if index_series:
                    # Chercher la valeur à la date de référence ou la plus proche
                    reference_index_value = None

                    # D'abord, essayer la date exacte
                    if reference_date in index_series:
                        reference_index_value = index_series[reference_date]
                    else:
                        # Sinon, prendre la date la plus proche avant ou égale à la référence
                        valid_dates = [
                            d for d in index_series.keys()
                            if d <= reference_date
                        ]
                        if valid_dates:
                            closest_date = max(valid_dates)
                            reference_index_value = index_series[closest_date]
                        else:
                            # Si aucune date antérieure, prendre la plus ancienne
                            earliest_date = min(index_series.keys())
                            reference_index_value = index_series[earliest_date]

                    if reference_index_value:
                        # Prix de référence = critère × valeur_index_à_la_date_de_référence
                        slice_reference_price = criteria_value * reference_index_value
                        total_reference_price += slice_reference_price

    return total_reference_price if total_reference_price > 0 else 1.0


def calculate_part_price_at_date_v3(part, target_date, index_data):
    """
    Nouvelle version qui calcule le prix selon le nouveau mode Fixed Criteria
    Prix = prix_référence + (valeur_tonnes × delta_index)
    """
    total_price = part.reference_price  # On part du prix de référence

    for slice_obj in part.slices.all():
        if slice_obj.slice_mode == "percentage":
            # Mode Cost Structure (ancien) - inchangé
            if slice_obj.percentage is None:
                continue

            slice_reference_value = part.reference_price * (
                slice_obj.percentage / 100)

            if slice_obj.component_type == 'indexed' and slice_obj.index_id:
                series = index_data.get(slice_obj.index_id, {})
                base_val = series.get(part.reference_date)
                current_val = series.get(target_date)

                if base_val and current_val and base_val != 0:
                    evolution_ratio = current_val / base_val
                    slice_current_value = slice_reference_value * evolution_ratio
                    # Pour le mode percentage, on remplace la part correspondante
                    total_price += (slice_current_value -
                                    slice_reference_value)

            elif slice_obj.component_type == 'fixed':
                # Rien à faire pour les tranches fixes en mode percentage
                pass

        elif slice_obj.slice_mode == "fixed_criteria":
            # Nouveau mode Fixed Criteria
            if slice_obj.criteria_value_tonnes is None or slice_obj.index_id is None:
                continue

            series = index_data.get(slice_obj.index_id, {})
            reference_val = series.get(
                part.reference_date)  # Valeur à la date de référence
            current_val = series.get(target_date)  # Valeur actuelle

            if reference_val and current_val:
                # Delta = (valeur_actuelle - valeur_référence) × tonnage
                delta_index = current_val - reference_val
                price_impact = slice_obj.criteria_value_tonnes * delta_index
                total_price += price_impact

    return max(total_price, 0)  # Éviter les prix négatifs


def extract_slice_data_v2(post_data):
    """Version mise à jour pour extraire les données des tranches"""
    slice_data = []
    i = 0
    while f"slice_label_{i}" in post_data:
        label = post_data.get(f"slice_label_{i}", "").strip()

        # Mode Cost Structure (ancien format)
        if f"slice_type_{i}" in post_data:
            component_type = post_data.get(f"slice_type_{i}", "")
            index_id = post_data.get(f"slice_index_{i}", "")
            percentage = post_data.get(f"slice_percentage_{i}", "")

            if label and component_type and percentage:
                slice_info = {
                    "label": label,
                    "component_type": component_type,
                    "percentage": float(percentage),
                    "index_id":
                    int(index_id) if index_id and index_id != "" else None,
                    "mode": "cost_structure"
                }
                slice_data.append(slice_info)

        # Mode Fixed Criteria (nouveau format simplifié)
        elif f"slice_value_{i}" in post_data:
            value_tonnes = post_data.get(f"slice_value_{i}", "")
            index_id = post_data.get(f"slice_index_{i}", "")

            if label and value_tonnes and index_id:
                slice_info = {
                    "label": label,
                    "component_type": "indexed",
                    "criteria_value_tonnes": float(value_tonnes),
                    "index_id": int(index_id),
                    "mode": "fixed_criteria"
                }
                slice_data.append(slice_info)

        i += 1
    return slice_data


def validate_slices(slice_data):
    """Valide les tranches selon le mode utilisé"""
    if not slice_data:
        return "At least one slice is required"

    # Vérifier le mode (tous les slices doivent être du même mode)
    modes = set(slice["mode"] for slice in slice_data)
    if len(modes) > 1:
        return "Cannot mix Cost Structure and Fixed Criteria modes"

    mode = modes.pop()

    if mode == "cost_structure":
        # Validation pour le mode Cost Structure (pourcentages = 100%)
        total_percentage = sum(slice["percentage"] for slice in slice_data)
        if abs(total_percentage - 100) > 0.1:
            return f"Sum of percentages must equal 100% (currently {total_percentage}%)"

        # Vérifier que les tranches indexées ont bien un index
        for slice_info in slice_data:
            if slice_info["component_type"] == "indexed" and not slice_info[
                    "index_id"]:
                return f"Slice '{slice_info['label']}' of type 'Indexed' must have an index selected"

    elif mode == "fixed_criteria":
        # Validation pour le mode Fixed Criteria
        for slice_info in slice_data:
            if not slice_info["index_id"]:
                return f"Slice '{slice_info['label']}' must have an index selected"
            if slice_info["criteria_value_tonnes"] <= 0:
                return f"Slice '{slice_info['label']}' must have a value greater than 0"

    return None


def create_slices_for_part_v2(part, slice_data, user):
    """Version mise à jour pour créer les tranches"""
    for slice_info in slice_data:
        slice_obj = Slice(part=part,
                          label=slice_info["label"],
                          component_type=slice_info["component_type"],
                          reference_date=part.reference_date)

        if slice_info["mode"] == "cost_structure":
            # Mode Cost Structure
            slice_obj.slice_mode = "percentage"
            slice_obj.percentage = slice_info["percentage"]
            if slice_info["component_type"] == "indexed" and slice_info[
                    "index_id"]:
                try:
                    index = user.userprofile.favorite_indexes.get(
                        id=slice_info["index_id"])
                    slice_obj.index = index
                except Index.DoesNotExist:
                    pass

        elif slice_info["mode"] == "fixed_criteria":
            # Mode Fixed Criteria
            slice_obj.slice_mode = "fixed_criteria"
            slice_obj.criteria_value_tonnes = slice_info[
                "criteria_value_tonnes"]
            try:
                index = user.userprofile.favorite_indexes.get(
                    id=slice_info["index_id"])
                slice_obj.index = index
            except Index.DoesNotExist:
                pass

        slice_obj.save()


@require_POST
@login_required
@require_POST
@login_required
def get_part_data(request, part_id):
    """Récupère les données d'une pièce avec ses tranches pour l'édition"""
    try:
        part = Part.objects.get(id=part_id, user=request.user)
        slices_data = []

        for slice_obj in part.slices.all():
            slice_data = {
                "label": slice_obj.label,
                "component_type": slice_obj.component_type,
                "index_id": slice_obj.index.id if slice_obj.index else None,
                "index_name":
                slice_obj.index.name if slice_obj.index else None,
            }

            # Ajouter les données spécifiques selon le mode
            if slice_obj.slice_mode == "percentage":
                # Mode Cost Structure
                slice_data["percentage"] = float(
                    slice_obj.percentage) if slice_obj.percentage else 0
                slice_data["slice_mode"] = "percentage"
            elif slice_obj.slice_mode == "fixed_criteria":
                # Mode Fixed Criteria
                slice_data["criteria_value_tonnes"] = float(
                    slice_obj.criteria_value_tonnes
                ) if slice_obj.criteria_value_tonnes else 0
                slice_data["slice_mode"] = "fixed_criteria"
            else:
                # Fallback pour les anciens enregistrements
                slice_data["percentage"] = float(
                    slice_obj.percentage) if slice_obj.percentage else 0
                slice_data["slice_mode"] = "percentage"

            slices_data.append(slice_data)

        data = {
            "name": part.name,
            "part_number": part.part_number or "",
            "reference_date": part.reference_date.strftime("%Y-%m-%d"),
            "reference_price": float(part.reference_price),
            "product_id": part.product.id if part.product else "",
            "slices": slices_data
        }

        return JsonResponse({"status": "success", "data": data})
    except Part.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "Pièce non trouvée"
        })


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
                "label":
                slice.label,
                "component_type":
                slice.component_type,
                "fixed_amount":
                float(slice.fixed_amount) if slice.fixed_amount else None,
                "percentage":
                float(slice.percentage) if slice.percentage else None,
                "index_id":
                slice.index.id if slice.index else None,
                "part_reference_price":
                float(slice.part.reference_price),
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
    products = Product.objects.filter(
        user=user).prefetch_related("parts__slices__index")

    # Récupérer les parts orphelines
    orphan_parts = Part.objects.filter(
        user=user, product__isnull=True).prefetch_related("slices__index")

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
                    part_current_price = calculate_part_price_at_date_v3(
                        part, latest_date, index_data)
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

    # Calcul pour les parts orphelines
    orphan_parts_prices = {}
    for part in orphan_parts:
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
                part_current_price = calculate_part_price_at_date_v3(
                    part, latest_date, index_data)
            else:
                part_current_price = part_reference_price
        else:
            # Pas d'index, le prix reste identique
            part_current_price = part_reference_price

        orphan_parts_prices[part.id] = {
            'reference': part_reference_price,
            'current': part_current_price
        }

    prices_data['orphan_parts'] = orphan_parts_prices

    return prices_data
