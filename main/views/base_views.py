from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.utils import timezone

# Imports de votre app
from main.models import Index, IndexValue, Product, Part, Slice, EmailVerification
from main.utils import get_user_index_data
from main.forms import CustomUserCreationForm, ContactForm, EmailVerificationForm, ResendCodeForm

# Imports Python standard
import json
from datetime import datetime, timedelta, date as datetime_date
import re

# Imports pour l'Excel
import pandas as pd
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    user_profile = request.user.userprofile
    favorites = user_profile.favorite_indexes.all()

    # === INDEX CHARTS (code existant) ===
    charts = []

    for index in favorites:
        values = IndexValue.objects.filter(index=index).order_by("date")

        if not values.exists():
            continue

        dates = [v.date for v in values]
        val = [v.value for v in values]

        latest_date = dates[-1]
        current_price = val[-1]

        def get_value_x_days_ago(days):
            target = latest_date - timedelta(days=days)
            margin = timedelta(days=7)
            candidates = [
                v.value for v in values if abs(v.date - target) <= margin
            ]
            return candidates[0] if candidates else None

        def variation(past_val):
            return round(((current_price - past_val) / past_val) *
                         100, 2) if past_val else None

        val_1m = get_value_x_days_ago(30)
        val_6m = get_value_x_days_ago(180)
        val_1y = get_value_x_days_ago(365)

        charts.append({
            "id": index.id,
            "name": index.name,
            "price": round(current_price, 2),
            "variation_1m": variation(val_1m),
            "variation_6m": variation(val_6m),
            "variation_1y": variation(val_1y),
            "mini_dates": json.dumps([d.strftime("%Y-%m-%d") for d in dates[-30:]]),
            "mini_values": json.dumps(val[-30:]),
            "last_update": latest_date.strftime("%Y-%m-%d"),
            "unit": index.unit,
            "category": index.category,
        })

    # === PRODUCT CHARTS (nouveau) ===
    products = Product.objects.filter(
        user=request.user).prefetch_related("parts__slices__index")
    product_charts = []

    try:
        index_data = get_user_index_data(request.user)
    except:
        index_data = {}

    for product in products:
        # Calculer le prix de référence total
        reference_price = product.total_reference_price()

        # Calculer le prix actuel
        current_price = calculate_product_current_price(product, index_data)

        # Calculer la variation depuis la date de référence
        variation_since_ref = None
        if reference_price and reference_price > 0:
            variation_since_ref = round(
                ((current_price - reference_price) / reference_price) * 100, 2)

        # Générer les données pour le mini-graphique
        mini_dates, mini_values = generate_product_mini_chart_data(
            product, index_data)

        # Trouver la dernière date de mise à jour
        last_update = get_product_last_update(product, index_data)

        product_charts.append({
            "id": product.id,
            "name": product.name,
            "reference_price": round(reference_price, 2) if reference_price else 0,
            "current_price": round(current_price, 2),
            "reference_date": product.reference_date.strftime("%Y-%m-%d"),
            "variation_since_ref": variation_since_ref,
            "mini_dates": json.dumps(mini_dates),
            "mini_values": json.dumps(mini_values),
            "last_update": last_update,
        })

    # Favoris IDs pour les étoiles
    favorite_ids = [index.id for index in favorites]

    return render(
        request,
        "dashboard.html",
        {
            "charts": charts,
            "product_charts": product_charts,
            "subscription": user_profile.subscription_plan,
            "favorite_ids": favorite_ids,
        })


def calculate_product_current_price(product, index_data):
    """Calcule le prix actuel d'un produit"""
    total_price = 0
    today = datetime_date.today()

    for part in product.parts.all():
        part_current_price = calculate_part_price_at_date(
            part, today, index_data)
        total_price += part_current_price

    return total_price


def calculate_part_price_at_date(part, target_date, index_data):
    """Calcule le prix d'une pièce à une date donnée"""
    total_price = 0

    for slice_obj in part.slices.all():
        slice_reference_value = part.reference_price * (slice_obj.percentage / 100)

        if slice_obj.component_type == 'indexed' and slice_obj.index_id and slice_obj.percentage:
            # Calcul pour tranches indexées
            series = index_data.get(slice_obj.index_id, {})
            base_val = series.get(part.reference_date)

            # Chercher la valeur la plus proche de target_date
            current_val = None
            if series:
                available_dates = [
                    d for d in series.keys() if d <= target_date
                ]
                if available_dates:
                    closest_date = max(available_dates)
                    current_val = series.get(closest_date)

            if base_val and current_val and base_val != 0:
                evolution_ratio = current_val / base_val
                slice_current_value = slice_reference_value * evolution_ratio
                total_price += slice_current_value
            else:
                # Pas de données d'index, utiliser la valeur de référence
                total_price += slice_reference_value

        elif slice_obj.component_type == 'fixed' and slice_obj.percentage:
            # Calcul pour tranches fixes - reste constant
            total_price += slice_reference_value

    return total_price


def generate_product_mini_chart_data(product, index_data):
    """Génère les données pour le mini-graphique d'un produit"""
    # Récupérer tous les index utilisés dans ce produit
    all_index_ids = set()
    for part in product.parts.all():
        for slice_obj in part.slices.all():
            if slice_obj.component_type == "indexed" and slice_obj.index_id:
                all_index_ids.add(slice_obj.index_id)

    if not all_index_ids:
        # Pas d'index, ligne horizontale depuis la date de référence
        ref_date = product.reference_date
        today = datetime_date.today()
        reference_price = product.total_reference_price()

        dates = []
        values = []
        current_date = ref_date

        # Générer des points mensuels
        while current_date <= today and len(dates) < 30:
            dates.append(current_date.strftime("%Y-%m-%d"))
            values.append(reference_price)

            # Passer au mois suivant
            if current_date.month == 12:
                current_date = datetime_date(current_date.year + 1, 1, 1)
            else:
                current_date = datetime_date(current_date.year, current_date.month + 1, 1)

        return dates, values

    # Récupérer toutes les dates disponibles après la date de référence
    all_dates = set()
    for index_id in all_index_ids:
        if index_id in index_data:
            index_dates = [
                d for d in index_data[index_id].keys()
                if d >= product.reference_date
            ]
            all_dates.update(index_dates)

    if not all_dates:
        return [], []

    # Trier et prendre les 30 dernières dates
    sorted_dates = sorted(all_dates)[-30:]

    dates = []
    values = []

    for date in sorted_dates:
        product_price = 0
        for part in product.parts.all():
            part_price = calculate_part_price_at_date(part, date, index_data)
            product_price += part_price

        dates.append(date.strftime("%Y-%m-%d"))
        values.append(round(product_price, 2))

    return dates, values


def get_product_last_update(product, index_data):
    """Trouve la dernière date de mise à jour d'un produit"""
    latest_date = product.reference_date

    for part in product.parts.all():
        for slice_obj in part.slices.all():
            if slice_obj.component_type == "indexed" and slice_obj.index_id:
                if slice_obj.index_id in index_data:
                    index_dates = list(index_data[slice_obj.index_id].keys())
                    if index_dates:
                        index_latest = max(index_dates)
                        if index_latest > latest_date:
                            latest_date = index_latest

    return latest_date.strftime("%Y-%m-%d")


@require_POST
def contact_view(request):
    """Vue pour traiter le formulaire de contact via AJAX"""
    try:
        # Récupération des données du formulaire
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        # Validation basique
        if not all([name, email, subject, message]):
            return JsonResponse(
                {'status': 'error', 'message': 'Tous les champs sont requis'},
                status=400)

        # Construction du message email
        email_subject = f"[IndexTracker Contact] {subject}"
        email_body = f"""
Nouveau message de contact depuis IndexTracker

Nom: {name}
Email: {email}
Sujet: {subject}

Message:
{message}

---
Envoyé depuis l'application IndexTracker
Utilisateur connecté: {request.user.username if request.user.is_authenticated else 'Anonyme'}
        """

        # Envoi de l'email
        send_mail(
            subject=email_subject,
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['indextracker.contact@gmail.com'],
            fail_silently=False,
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Votre message a été envoyé avec succès!'
        })

    except Exception as e:
        return JsonResponse(
            {'status': 'error', 'message': 'Une erreur est survenue lors de l\'envoi. Veuillez réessayer.'},
            status=500)


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("main:dashboard")
        else:
            return render(request, "login.html", {"error": "Identifiants invalides."})

    return render(request, "login.html")


def is_admin(user):
    return user.is_superuser


@user_passes_test(is_admin)
def upload_excel(request):
    """Vue pour l'upload de fichier Excel par l'admin"""
    if request.method == "POST":
        try:
            # Vérifier qu'un fichier a été uploadé
            if 'excel_file' not in request.FILES:
                messages.error(request, "Aucun fichier sélectionné.")
                return render(request, "admin/import_excel.html")

            excel_file = request.FILES['excel_file']

            # Vérifier l'extension du fichier
            if not excel_file.name.endswith(('.xlsx', '.xls')):
                messages.error(request, "Le fichier doit être un fichier Excel (.xlsx ou .xls).")
                return render(request, "admin/import_excel.html")

            # Option pour remplacer les données existantes
            replace_existing = request.POST.get('replace_existing', False)

            # Traiter le fichier
            result = process_excel_file_optimized(excel_file, replace_existing=replace_existing)

            if result['success']:
                message = f"✅ Import réussi ! {result['indexes_count']} index"
                if 'values_created' in result and 'values_updated' in result:
                    message += f", {result['values_created']} valeurs créées, {result['values_updated']} mises à jour."
                else:
                    message += f" et {result['values_count']} valeurs importées."
                messages.success(request, message)
            else:
                messages.error(request, f"❌ Erreur lors de l'import : {result['error']}")

        except Exception as e:
            logger.error(f"Erreur upload Excel: {e}")
            messages.error(request, f"❌ Erreur inattendue : {str(e)}")

    return render(request, "admin/import_excel.html")


def process_excel_file_optimized(excel_file, replace_existing=False):
    """
    Traite un fichier Excel et importe les données d'index de manière optimisée

    Args:
        excel_file: Fichier Excel à traiter
        replace_existing: Si True, remplace les valeurs existantes. Si False, les ignore.
    """
    try:
        import time
        start_time = time.time()

        if replace_existing:
            print("🔄 MODE REMPLACEMENT: Les valeurs existantes seront mises à jour")
        else:
            print("➕ MODE AJOUT: Seules les nouvelles valeurs seront ajoutées")

        # Analyser les noms d'index existants en base
        print(f"\n🔍 ANALYSE DES INDEX EXISTANTS EN BASE:")
        existing_indexes = Index.objects.all()
        print(f"   Total index en base: {existing_indexes.count()}")

        # Créer un mapping des noms existants pour faciliter la correspondance
        existing_names = {}
        for idx in existing_indexes:
            value_count = IndexValue.objects.filter(index=idx).count()
            existing_names[idx.name] = value_count

        # Montrer quelques exemples d'index existants pour comparaison
        sample_existing = list(existing_indexes[:10])
        print(f"   Exemples d'index existants:")
        for i, idx in enumerate(sample_existing):
            value_count = existing_names[idx.name]
            print(f"      {i+1}. '{idx.name}' → {value_count} valeurs")

        # Analyser les patterns de noms pour identifier la logique
        print(f"\n🔍 ANALYSE DES PATTERNS DE NOMS:")
        bdsv_examples = [name for name in existing_names.keys() if 'BDSV' in name]
        caef_examples = [name for name in existing_names.keys() if 'CAEF' in name]
        almag_examples = [name for name in existing_names.keys() if 'ALMAG' in name]

        if bdsv_examples:
            print(f"   BDSV examples: {bdsv_examples[:3]}")
        if caef_examples:
            print(f"   CAEF examples: {caef_examples[:3]}")
        if almag_examples:
            print(f"   ALMAG examples: {almag_examples[:3]}")

        # Lire le fichier Excel (feuille "1. BDD")
        df = pd.read_excel(excel_file, sheet_name="1. BDD", header=0)
        print(f"📄 Fichier lu: {len(df)} lignes, {len(df.columns)} colonnes")

        # DEBUG: Analyser AU MOINS LA MOITIÉ des lignes pour voir le problème
        debug_lines = max(10, len(df) // 2)  # Au moins 10, ou la moitié du fichier
        print(f"\n🔍 DIAGNOSTIC DE {debug_lines} LIGNES (sur {len(df)}):")
        for i in range(min(debug_lines, len(df))):
            row = df.iloc[i]

            # Extraire les métadonnées comme dans le code principal
            index_type = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            index_subtype = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
            source = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
            designation = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
            unit = str(row.iloc[7]).strip() if pd.notna(row.iloc[7]) else "€/t"

            # Construire le nom comme dans le code principal
            base_name = f"{source} - {designation}" if source else designation

            if index_type and index_subtype:
                category = f"{index_type} - {index_subtype}"
                index_name = f"{base_name} ({category})" if category != "Raw material - Brass" else base_name
            elif index_type:
                category = index_type
                index_name = base_name
            else:
                category = "Autre"
                index_name = base_name

            # Vérifier pourquoi cette ligne serait ignorée
            will_be_ignored = not designation or designation.lower() in ['nan', '', 'none']

            print(f"   Ligne {i+1}:")
            print(f"      Type: '{index_type}' | Type2: '{index_subtype}'")
            print(f"      Source: '{source}' | Designation: '{designation}'")
            print(f"      Unit: '{unit}' | Category: '{category}'")
            print(f"      Index name final: '{index_name}'")
            print(f"      SERA IGNORÉE: {will_be_ignored} {'❌' if will_be_ignored else '✅'}")

            # Détecter les problèmes de métadonnées
            problems = []
            if unit == "€/t":  # Valeur par défaut = problème
                problems.append("UNITÉ PAR DÉFAUT")
            if category == "Autre":  # Catégorie par défaut = problème
                problems.append("CATÉGORIE PAR DÉFAUT") 
            if not source:
                problems.append("PAS DE SOURCE")
            if not index_type:
                problems.append("PAS DE TYPE")

            if problems:
                print(f"      ⚠️ PROBLÈMES DÉTECTÉS: {', '.join(problems)}")

            # Compter les valeurs non vides pour cette ligne
            if not will_be_ignored:
                non_empty_values = 0
                for col_idx in range(8, min(len(row), 20)):  # Tester les 12 premières colonnes de dates
                    if pd.notna(row.iloc[col_idx]) and row.iloc[col_idx] != "" and row.iloc[col_idx] != 0:
                        non_empty_values += 1
                print(f"      Valeurs non vides (12 premières dates): {non_empty_values}")
                if non_empty_values == 0:
                    print(f"      ❌ AUCUNE VALEUR → INDEX VIDE !")
            print()

        # Colonnes de valeurs (à partir de la colonne 8)
        date_columns = df.columns[8:].tolist()
        date_columns = [col for col in date_columns if col and str(col).strip()]

        # Compter combien de lignes seront vraiment traitées
        valid_lines = 0
        ignored_lines = 0
        ignored_reasons = {"no_designation": 0, "short_row": 0, "other": 0}

        for row_index, row in df.iterrows():
            if len(row) < 8:
                ignored_lines += 1
                ignored_reasons["short_row"] += 1
                continue

            designation = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

            if not designation or designation.lower() in ['nan', '', 'none']:
                ignored_lines += 1
                ignored_reasons["no_designation"] += 1
                continue

            valid_lines += 1

        print(f"📊 RÉSUMÉ AVANT TRAITEMENT:")
        print(f"   Total lignes fichier: {len(df)}")
        print(f"   Lignes valides: {valid_lines}")
        print(f"   Lignes ignorées: {ignored_lines}")
        print(f"      - Trop courtes: {ignored_reasons['short_row']}")
        print(f"      - Sans désignation: {ignored_reasons['no_designation']}")
        print(f"   Dates à traiter: {len(date_columns)}")

        # Parser toutes les dates françaises une seule fois
        parsed_dates = {}
        for date_col in date_columns:
            parsed_dates[date_col] = parse_french_date_clean(date_col)

        valid_dates = len([d for d in parsed_dates.values() if d])
        print(f"   Dates valides parsées: {valid_dates}/{len(date_columns)}")

        # Préparer tous les objets en mémoire
        indexes_to_create = []
        values_to_create = []

        # Traiter chaque ligne
        processed_lines = 0
        for row_index, row in df.iterrows():
            try:
                # Vérifier que la ligne a assez de colonnes
                if len(row) < 8:
                    continue

                # Extraction des métadonnées
                index_type = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                index_subtype = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                source = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
                designation = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
                unit = str(row.iloc[7]).strip() if pd.notna(row.iloc[7]) else "€/t"

                # Ignorer les lignes sans désignation valide
                if not designation or designation.lower() in ['nan', '', 'none']:
                    continue

                # Essayer de matcher les noms existants d'abord

                # Tentative 1: Nom exact de la désignation
                candidate_names = [designation]

                # Tentative 2: Source + désignation (si source pas déjà dans désignation)
                if source and not designation.startswith(source):
                    candidate_names.append(f"{source} - {designation}")

                # Tentative 3: Variantes courantes observées
                if source and designation.startswith(source):
                    # Enlever le préfixe source dupliqué
                    clean_designation = designation[len(source):].strip(' -')
                    candidate_names.append(f"{source} - {clean_designation}")

                # Chercher une correspondance exacte avec les index existants
                index_name = None
                for candidate in candidate_names:
                    if candidate in existing_names:
                        index_name = candidate
                        if processed_lines < 100:  # Debug pour les premières lignes
                            print(f"      ✅ MATCH TROUVÉ: '{candidate}' existe déjà avec {existing_names[candidate]} valeurs")
                        break

                # Si aucun match, utiliser le premier candidat
                if not index_name:
                    index_name = candidate_names[0]
                    if processed_lines < 5:
                        print(f"      ➕ NOUVEAU: '{index_name}'")

                # Définir la catégorie
                if index_type and index_subtype and index_subtype != "Brass":
                    category = f"{index_type} - {index_subtype}"
                elif index_type:
                    category = index_type
                else:
                    category = "Autre"

                # DEBUG: Montrer la transformation pour les premiers exemples
                if processed_lines < 5:
                    print(f"      🔄 Candidats testés: {candidate_names}")
                    print(f"      📂 Nom final: '{index_name}'")
                    print(f"      📂 Catégorie: '{category}'")

                # Stocker les données d'index
                index_data = {
                    'name': index_name,
                    'unit': unit,
                    'category': category,
                    'row_index': row_index
                }
                indexes_to_create.append(index_data)

                # Traitement des valeurs
                values_for_this_row = 0
                for date_col in date_columns:
                    if date_col in df.columns:
                        value = row[date_col]

                        # Ignorer les valeurs vides ou non numériques
                        if pd.isna(value) or value == "":
                            continue

                        try:
                            value_float = float(value)
                            if value_float == 0:  # Ignorer les valeurs zéro
                                continue
                        except (ValueError, TypeError):
                            continue

                        # Utiliser la date pré-parsée
                        date_obj = parsed_dates.get(date_col)
                        if date_obj:
                            values_to_create.append({
                                'index_name': index_name,
                                'value': value_float,
                                'date': date_obj
                            })
                            values_for_this_row += 1

                processed_lines += 1

                # Debug occasionnel
                if processed_lines <= 5 or processed_lines % 50 == 0:
                    print(f"   ✅ Ligne {row_index+1}: '{index_name}' → {values_for_this_row} valeurs")

            except Exception as e:
                print(f"   ❌ Erreur ligne {row_index + 1}: {e}")
                continue

        elapsed_prep = time.time() - start_time
        print(f"📊 Préparation terminée: {len(indexes_to_create)} index, {len(values_to_create)} valeurs ({elapsed_prep:.1f}s)")

        # Analyser aussi les problèmes de métadonnées
        print(f"\n🔍 ANALYSE DES PROBLÈMES DE MÉTADONNÉES:")
        metadata_issues = {
            "default_unit": 0,  # Unité par défaut
            "default_category": 0,  # Catégorie par défaut  
            "no_source": 0,  # Pas de source
            "no_type": 0,  # Pas de type
            "no_values": 0,  # Pas de valeurs
        }

        for idx_data in indexes_to_create:
            if idx_data['unit'] == "€/t":
                metadata_issues["default_unit"] += 1
            if idx_data['category'] == "Autre":
                metadata_issues["default_category"] += 1

        # Compter les index sans valeurs
        index_value_counts = {}
        for val_data in values_to_create:
            idx_name = val_data['index_name']
            index_value_counts[idx_name] = index_value_counts.get(idx_name, 0) + 1

        indexes_without_values = 0
        for idx_data in indexes_to_create:
            if idx_data['name'] not in index_value_counts:
                indexes_without_values += 1
                metadata_issues["no_values"] += 1

        print(f"   Index avec unité par défaut (€/t): {metadata_issues['default_unit']}")
        print(f"   Index avec catégorie par défaut (Autre): {metadata_issues['default_category']}")
        print(f"   Index SANS VALEURS: {metadata_issues['no_values']}")

        # Analyser aussi les doublons potentiels
        print(f"\n🔍 ANALYSE DES DOUBLONS:")
        name_counts = {}
        for idx_data in indexes_to_create:
            name = idx_data['name']
            if name not in name_counts:
                name_counts[name] = []
            name_counts[name].append(idx_data)

        # Montrer les doublons détectés
        duplicates_found = 0
        for name, occurrences in name_counts.items():
            if len(occurrences) > 1:
                duplicates_found += 1
                if duplicates_found <= 10:  # Montrer les 10 premiers doublons
                    print(f"   DOUBLON '{name}': {len(occurrences)} occurrences")
                    for i, occ in enumerate(occurrences[:3]):  # Max 3 par doublon
                        print(f"      {i+1}. Ligne {occ['row_index']+1}: unit='{occ['unit']}', category='{occ['category']}'")

        print(f"   Total doublons détectés: {duplicates_found}")
        unique_names = len(name_counts)
        print(f"   Noms uniques: {unique_names}")
        print(f"   Ratio de déduplication: {len(indexes_to_create)} → {unique_names} ({(1-unique_names/len(indexes_to_create))*100:.1f}% supprimés)")

        # Import en base avec bulk_create
        with transaction.atomic():
            # Étape 1: Créer tous les index
            index_objects = {}
            indexes_created = 0

            # Déduplication en mémoire
            unique_indexes = {}
            for idx_data in indexes_to_create:
                idx_name = idx_data['name']
                if idx_name not in unique_indexes:
                    unique_indexes[idx_name] = idx_data

            print(f"📦 Index après déduplication: {len(unique_indexes)}")

            # Si mode remplacement, supprimer les anciennes valeurs
            if replace_existing:
                print("🗑️ Suppression des anciennes valeurs...")
                deleted_count = 0
                for idx_name, index_obj in existing_names.items():
                    if idx_name in unique_indexes:
                        try:
                            index_instance = Index.objects.get(name=idx_name)
                            deleted = IndexValue.objects.filter(index=index_instance).delete()
                            deleted_count += deleted[0] if deleted[0] else 0
                        except Index.DoesNotExist:
                            pass
                print(f"   📊 {deleted_count} anciennes valeurs supprimées")

            for idx_name, idx_data in unique_indexes.items():
                index_obj, created = Index.objects.get_or_create(
                    name=idx_name,
                    defaults={
                        'unit': idx_data['unit'],
                        'category': idx_data['category']
                    }
                )
                index_objects[idx_name] = index_obj
                if created:
                    indexes_created += 1

            # Étape 2: Préparer toutes les valeurs
            index_value_objects = []
            for val_data in values_to_create:
                if val_data['index_name'] in index_objects:
                    index_value_objects.append(
                        IndexValue(
                            index=index_objects[val_data['index_name']],
                            value=val_data['value'],
                            date=val_data['date']
                        )
                    )

            # Étape 3: Import en masse avec possibilité de mise à jour
            values_created = 0
            values_updated = 0
            batch_size = 1000

            print(f"📦 Import de {len(index_value_objects)} valeurs par batch de {batch_size}...")

            if replace_existing:
                # Mode remplacement: créer directement (anciennes valeurs déjà supprimées)
                for i in range(0, len(index_value_objects), batch_size):
                    batch = index_value_objects[i:i + batch_size]
                    created_objects = IndexValue.objects.bulk_create(batch, ignore_conflicts=False)
                    values_created += len(created_objects)
                    if i % 5000 == 0:
                        print(f"   📊 Batch {i//batch_size + 1}: {len(created_objects)} valeurs créées")
            else:
                # Mode ajout: gestion des conflits
                for i in range(0, len(index_value_objects), batch_size):
                    batch = index_value_objects[i:i + batch_size]

                    # Essayer bulk_create sans ignore_conflicts d'abord
                    try:
                        created_objects = IndexValue.objects.bulk_create(batch, ignore_conflicts=False)
                        values_created += len(created_objects)
                        if i % 5000 == 0:
                            print(f"   📊 Batch {i//batch_size + 1}: {len(created_objects)} nouvelles valeurs")
                    except Exception as e:
                        print(f"   ⚠️ Conflits détectés dans le batch {i//batch_size + 1}, passage en mode mise à jour...")
                        # Si il y a des conflits, traiter individuellement
                        for value_obj in batch:
                            existing_value = IndexValue.objects.filter(
                                index=value_obj.index,
                                date=value_obj.date
                            ).first()

                            if existing_value:
                                # Mettre à jour la valeur existante
                                existing_value.value = value_obj.value
                                existing_value.save()
                                values_updated += 1
                            else:
                                # Créer une nouvelle valeur
                                value_obj.save()
                                values_created += 1

                        if i % 5000 == 0:
                            print(f"   📊 Batch {i//batch_size + 1}: traitement individuel terminé")

            print(f"📊 Résultat final: {values_created} créées, {values_updated} mises à jour")

        total_time = time.time() - start_time
        print(f"✅ Import terminé: {indexes_created} index, {values_created} valeurs créées, {values_updated} mises à jour en {total_time:.1f}s")

        # Vérifier quels index restent vides après l'import
        print(f"\n🔍 VÉRIFICATION POST-IMPORT:")
        empty_indexes = []
        filled_indexes = []

        for idx_name, index_obj in index_objects.items():
            value_count = IndexValue.objects.filter(index=index_obj).count()
            if value_count == 0:
                empty_indexes.append(idx_name)
            else:
                filled_indexes.append((idx_name, value_count))

        print(f"   📊 Index avec valeurs: {len(filled_indexes)}")
        print(f"   ❌ Index vides: {len(empty_indexes)}")

        if empty_indexes:
            print(f"\n❌ INDEX RESTÉS VIDES (premiers 10):")
            for i, idx_name in enumerate(empty_indexes[:10]):
                print(f"   {i+1}. {idx_name}")
            if len(empty_indexes) > 10:
                print(f"   ... et {len(empty_indexes) - 10} autres")

        if filled_indexes:
            print(f"\n✅ INDEX REMPLIS (premiers 5):")
            for i, (idx_name, count) in enumerate(filled_indexes[:5]):
                print(f"   {i+1}. {idx_name}: {count} valeurs")

        return {
            'success': True,
            'indexes_count': indexes_created,
            'values_created': values_created,
            'values_updated': values_updated,
            'values_count': values_created + values_updated,
            'empty_indexes_count': len(empty_indexes),
            'filled_indexes_count': len(filled_indexes)
        }

    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def parse_french_date_clean(col_name):
    """Parse une date française (format: mars-21, févr-24, etc.)"""
    try:
        month_mapping = {
            'janv': 1, 'févr': 2, 'mars': 3, 'avr': 4, 'mai': 5, 'juin': 6,
            'juil': 7, 'août': 8, 'sept': 9, 'oct': 10, 'nov': 11, 'déc': 12
        }

        col_str = str(col_name).strip()

        if '-' in col_str:
            parts = col_str.split('-')
            if len(parts) == 2:
                month_str, year_str = parts

                if month_str in month_mapping:
                    month = month_mapping[month_str]
                    year_int = int(year_str)

                    # Déterminer le siècle
                    if year_int < 50:
                        year = 2000 + year_int
                    else:
                        year = 1900 + year_int

                    return datetime(year, month, 1).date()

    except Exception:
        pass

    return None


@user_passes_test(is_admin)
def cleanup_duplicate_indexes(request):
    """Vue pour nettoyer les index en doublon"""

    if request.method == "POST" and request.POST.get("confirm_cleanup"):
        result = perform_cleanup_duplicates()

        if result['success']:
            messages.success(
                request,
                f"✅ Nettoyage terminé ! {result['merged_count']} doublons fusionnés, "
                f"{result['deleted_count']} index vides supprimés, "
                f"{result['values_moved']} valeurs déplacées."
            )
        else:
            messages.error(request, f"❌ Erreur : {result['error']}")

        return redirect('main:cleanup_duplicates')

    # Analyser les doublons pour affichage
    duplicates_analysis = analyze_duplicates()

    return render(request, "admin/cleanup_duplicates.html", {
        "duplicates": duplicates_analysis['duplicates'],
        "total_duplicates": duplicates_analysis['total_count'],
        "estimated_cleanup": duplicates_analysis['estimated_cleanup']
    })


def analyze_duplicates():
    """Analyser les doublons existants"""

    all_indexes = Index.objects.all()
    duplicates = {}

    for index in all_indexes:
        # Identifier le nom "propre" (sans doublons de préfixe)
        clean_name = clean_index_name(index.name)

        if clean_name not in duplicates:
            duplicates[clean_name] = []

        duplicates[clean_name].append({
            'id': index.id,
            'name': index.name,
            'values_count': IndexValue.objects.filter(index=index).count()
        })

    # Garder seulement les groupes avec plusieurs index
    real_duplicates = {
        clean_name: indexes 
        for clean_name, indexes in duplicates.items() 
        if len(indexes) > 1
    }

    # Statistiques
    total_count = sum(len(indexes) - 1 for indexes in real_duplicates.values())
    estimated_cleanup = sum(
        sum(idx['values_count'] for idx in indexes[1:])  # Valeurs des doublons à fusionner
        for indexes in real_duplicates.values()
    )

    return {
        'duplicates': real_duplicates,
        'total_count': total_count,
        'estimated_cleanup': estimated_cleanup
    }


def clean_index_name(name):
    """Nettoyer un nom d'index pour identifier les doublons"""

    # Pattern pour "ALMAG - ALMAG - Brass bar" → "ALMAG - Brass bar"
    pattern1 = r'^([A-Z]+) - \1 - (.+)$'
    match1 = re.match(pattern1, name)
    if match1:
        return f"{match1.group(1)} - {match1.group(2)}"

    # Pattern pour "ALMAG - ALMAG Brass bar" → "ALMAG Brass bar"  
    pattern2 = r'^([A-Z]+) - \1 (.+)$'
    match2 = re.match(pattern2, name)
    if match2:
        return f"{match2.group(1)} - {match2.group(2)}"

    return name


def perform_cleanup_duplicates():
    """Effectuer le nettoyage des doublons"""

    try:
        with transaction.atomic():
            duplicates_analysis = analyze_duplicates()
            duplicates = duplicates_analysis['duplicates']

            merged_count = 0
            deleted_count = 0
            values_moved = 0

            for clean_name, index_group in duplicates.items():
                # Trier par nombre de valeurs (descendant) pour garder le plus rempli
                index_group.sort(key=lambda x: x['values_count'], reverse=True)

                # Le premier (plus rempli) devient le principal
                main_index_data = index_group[0]
                main_index = Index.objects.get(id=main_index_data['id'])

                # Préférer le nom le plus "propre" (le plus court généralement)
                shortest_name = min(idx['name'] for idx in index_group if idx['values_count'] > 0)
                if main_index.name != shortest_name:
                    main_index.name = shortest_name
                    main_index.save()

                # Fusionner les doublons dans le principal
                for duplicate_data in index_group[1:]:
                    duplicate_index = Index.objects.get(id=duplicate_data['id'])

                    # Déplacer toutes les valeurs vers l'index principal
                    values_to_move = IndexValue.objects.filter(index=duplicate_index)
                    moved = 0

                    for value in values_to_move:
                        # Vérifier qu'il n'y a pas déjà une valeur pour cette date
                        existing = IndexValue.objects.filter(
                            index=main_index,
                            date=value.date
                        ).first()

                        if not existing:
                            value.index = main_index
                            value.save()
                            moved += 1
                        else:
                            # Si conflit, garder la valeur la plus récente
                            value.delete()

                    values_moved += moved

                    # Supprimer l'index doublon (maintenant vide)
                    duplicate_index.delete()
                    deleted_count += 1

                merged_count += 1

            return {
                'success': True,
                'merged_count': merged_count,
                'deleted_count': deleted_count,
                'values_moved': values_moved
            }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def register_view(request):
    """Vue d'inscription avec vérification email"""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Créer l'utilisateur (désactivé par défaut)
            user = form.save()

            # Créer le code de vérification
            verification, created = EmailVerification.objects.get_or_create(user=user)
            if not created:
                verification.verification_code = EmailVerification.generate_code()
                verification.created_at = timezone.now()
                verification.is_verified = False
                verification.save()

            # Envoyer l'email de vérification
            if send_verification_email(user, verification.verification_code):
                messages.success(request, 'Un code de vérification a été envoyé à votre adresse email.')
                return redirect('main:verify_email', user_id=user.id)
            else:
                messages.error(request, 'Erreur lors de l\'envoi de l\'email. Veuillez réessayer.')
                user.delete()

    else:
        form = CustomUserCreationForm()

    return render(request, "register.html", {"form": form})


def home(request):
    return render(request, "home.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("main:home")


def search_index(request):
    term = request.GET.get('term', '')
    results = []

    if term:
        indexes = Index.objects.filter(name__icontains=term)[:10]
        results = [{'id': index.id, 'name': index.name} for index in indexes]

    return JsonResponse(results, safe=False)


@login_required
def choose_primary_index(request):
    user_profile = request.user.userprofile
    max_changes = 3

    if user_profile.subscription_plan != 'free':
        return redirect('main:dashboard')

    if request.method == 'POST':
        new_index_id = request.POST.get('index_id')
        if new_index_id:
            new_index = Index.objects.get(id=new_index_id)
            if user_profile.primary_index != new_index:
                if user_profile.primary_index_change_count >= max_changes:
                    return render(request, "choose_primary_index.html", {
                        "indexes": Index.objects.all(),
                        "error": "Vous avez atteint la limite de modifications."
                    })
                user_profile.primary_index = new_index
                user_profile.primary_index_change_count += 1
                user_profile.save()
                return redirect('main:dashboard')

    return render(request, "choose_primary_index.html", {
        "indexes": Index.objects.all(),
        "current_index": user_profile.primary_index
    })


def verify_email(request, user_id):
    """Vue pour vérifier le code email"""
    try:
        user = User.objects.get(id=user_id, is_active=False)
        verification = EmailVerification.objects.get(user=user)
    except (User.DoesNotExist, EmailVerification.DoesNotExist):
        messages.error(request, 'Lien de vérification invalide.')
        return redirect('main:register')

    if verification.is_verified:
        messages.info(request, 'Votre compte est déjà vérifié.')
        return redirect('main:login')

    if request.method == "POST":
        form = EmailVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['verification_code']

            if verification.is_expired():
                messages.error(request, 'Le code a expiré. Demandez un nouveau code.')
            elif verification.verification_code == code:
                # Code correct - activer le compte
                user.is_active = True
                user.save()
                verification.is_verified = True
                verification.save()

                messages.success(request, 'Votre compte a été vérifié avec succès !')
                login(request, user)
                return redirect('main:dashboard')
            else:
                messages.error(request, 'Code incorrect. Veuillez réessayer.')
    else:
        form = EmailVerificationForm()

    return render(request, "verify_email.html", {
        "form": form,
        "user": user,
        "email": user.email,
        "is_expired": verification.is_expired()
    })


def resend_verification_code(request, user_id):
    """Vue pour renvoyer un code de vérification"""
    try:
        user = User.objects.get(id=user_id, is_active=False)
        verification = EmailVerification.objects.get(user=user)
    except (User.DoesNotExist, EmailVerification.DoesNotExist):
        messages.error(request, 'Utilisateur non trouvé.')
        return redirect('main:register')

    if verification.is_verified:
        messages.info(request, 'Votre compte est déjà vérifié.')
        return redirect('main:login')

    # Générer un nouveau code
    verification.verification_code = EmailVerification.generate_code()
    verification.created_at = timezone.now()
    verification.save()

    # Envoyer le nouveau code
    if send_verification_email(user, verification.verification_code):
        messages.success(request, 'Un nouveau code a été envoyé à votre adresse email.')
    else:
        messages.error(request, 'Erreur lors de l\'envoi de l\'email. Veuillez réessayer.')

    return redirect('main:verify_email', user_id=user.id)


def send_verification_email(user, code):
    """Fonction utilitaire pour envoyer l'email de vérification"""
    subject = 'Vérification de votre compte IndexTracker'
    message = f"""
Bonjour {user.username},

Merci de vous être inscrit sur IndexTracker !

Votre code de vérification est : {code}

Ce code expire dans 15 minutes.

Si vous n'avez pas créé de compte, ignorez cet email.

Cordialement,
L'équipe IndexTracker
    """

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Erreur envoi email: {e}")
        return False


@login_required
def upgrade_plan_view(request):
    """Affiche la page d'upgrade des plans"""
    return render(request, 'upgrade_plan.html')


@login_required
@require_POST
def upgrade_plan_api(request):
    """API pour changer de plan"""
    try:
        data = json.loads(request.body)
        new_plan = data.get('new_plan')

        # Validation du plan
        valid_plans = ['free', '5_index', '10_index', 'premium']
        if new_plan not in valid_plans:
            return JsonResponse({
                'success': False,
                'message': 'Invalid plan selected'
            })

        user_profile = request.user.userprofile
        old_plan = user_profile.subscription_plan

        # Vérification si c'est un vrai changement
        if old_plan == new_plan:
            return JsonResponse({
                'success': False,
                'message': 'You are already on this plan'
            })

        # Vérification des limites pour un downgrade
        if new_plan != 'premium':
            # Obtenir la nouvelle limite
            plan_limits = {
                'free': 1,
                '5_index': 5,
                '10_index': 10,
            }
            new_limit = plan_limits.get(new_plan, 1)
            current_favorites = user_profile.favorite_indexes.count()

            if current_favorites > new_limit:
                return JsonResponse({
                    'success': False,
                    'message': f'You have {current_favorites} indexes but the {new_plan} plan only allows {new_limit}. Please remove some indexes first.'
                })

        # Effectuer le changement
        user_profile.subscription_plan = new_plan
        user_profile.save()

        # Log du changement
        print(f"User {request.user.username} changed plan from {old_plan} to {new_plan}")

        return JsonResponse({
            'success': True,
            'message': f'Successfully changed to {new_plan} plan',
            'old_plan': old_plan,
            'new_plan': new_plan
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request format'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while changing your plan'
        })