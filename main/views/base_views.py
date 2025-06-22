from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin.views.decorators import staff_member_required
from datetime import datetime, timedelta
from main.models import Index, IndexValue, Product, Part, Slice
from main.utils import get_user_index_data
import json
from main.forms import CustomUserCreationForm
from datetime import date as datetime_date


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
            candidates = [v.value for v in values if abs(v.date - target) <= margin]
            return candidates[0] if candidates else None

        def variation(past_val):
            return round(((current_price - past_val) / past_val) * 100, 2) if past_val else None

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
    products = Product.objects.filter(user=request.user).prefetch_related("parts__slices__index")
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
            variation_since_ref = round(((current_price - reference_price) / reference_price) * 100, 2)

        # Générer les données pour le mini-graphique
        mini_dates, mini_values = generate_product_mini_chart_data(product, index_data)

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

    return render(request, "dashboard.html", {
        "charts": charts,
        "product_charts": product_charts,  # ✨ NOUVEAU
        "subscription": user_profile.subscription_plan,
        "favorite_ids": favorite_ids,
    })


def calculate_product_current_price(product, index_data):
    """Calcule le prix actuel d'un produit"""
    total_price = 0
    today = datetime_date.today()

    for part in product.parts.all():
        part_current_price = calculate_part_price_at_date(part, today, index_data)
        total_price += part_current_price

    return total_price


def calculate_part_price_at_date(part, target_date, index_data):
    """Calcule le prix d'une pièce à une date donnée (copié de prix_indexes_view)"""
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
                available_dates = [d for d in series.keys() if d <= target_date]
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
            index_dates = [d for d in index_data[index_id].keys() if d >= product.reference_date]
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


# Reste du code existant (login_view, register_view, etc.)
def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("main:dashboard")
        else:
            return render(request, "login.html",
                          {"error": "Identifiants invalides."})

    return render(request, "login.html")


def is_admin(user):
    return user.is_superuser


@user_passes_test(is_admin)
def upload_excel(request):
    return HttpResponse(
        "<h2>Upload Excel</h2><p>Formulaire d'upload de fichier Excel réservé à l'administrateur.</p>"
    )


def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("main:dashboard")
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
                    return render(
                        request, "choose_primary_index.html", {
                            "indexes": Index.objects.all(),
                            "error": "Vous avez atteint la limite de modifications."
                        })
                user_profile.primary_index = new_index
                user_profile.primary_index_change_count += 1
                user_profile.save()
                return redirect('main:dashboard')

    return render(
        request, "choose_primary_index.html", {
            "indexes": Index.objects.all(),
            "current_index": user_profile.primary_index
        })