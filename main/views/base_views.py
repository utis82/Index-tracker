from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin.views.decorators import staff_member_required
import pandas as pd
from datetime import datetime
from main.models import Index, IndexValue
import json
from main.forms import CustomUserCreationForm  #


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


@login_required
def dashboard(request):
    user_profile = request.user.userprofile
    favorites = user_profile.favorite_indexes.all()

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
            target = latest_date - pd.Timedelta(days=days)
            margin = pd.Timedelta(days=7)
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


    # ✅ Ajout nécessaire pour permettre l'affichage des étoiles dans le template
    favorite_ids = [index.id for index in favorites]

    return render(request, "dashboard.html", {
        "charts": charts,
        "subscription": user_profile.subscription_plan,
        "favorite_ids": favorite_ids,  # 🔥 ligne ajoutée
    })



def is_admin(user):
    return user.is_superuser


@user_passes_test(is_admin)
def upload_excel(request):
    return HttpResponse(
        "<h2>Upload Excel</h2><p>Formulaire d’upload de fichier Excel réservé à l’administrateur.</p>"
    )


def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # connexion directe après création
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
