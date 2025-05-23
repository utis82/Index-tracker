from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin.views.decorators import staff_member_required
import pandas as pd
from datetime import datetime
from main.models import Index, IndexValue
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from django.http import JsonResponse


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

        if values.exists():
            dates = [v.date for v in values]
            val = [v.value for v in values]

            fig, ax = plt.subplots(figsize=(4, 2))
            ax.plot(dates, val, marker='o')
            ax.set_title(index.name)
            ax.set_xlabel("Date")
            ax.set_ylabel("Valeur")
            ax.grid(True)

            buffer = BytesIO()
            plt.tight_layout()
            fig.autofmt_xdate()
            plt.savefig(buffer, format="png")
            buffer.seek(0)
            image_png = buffer.getvalue()
            buffer.close()
            chart = base64.b64encode(image_png).decode("utf-8")
            charts.append({"name": index.name, "chart": chart})
            plt.close(fig)

    return render(
        request,
        "dashboard.html",
        {
            "charts": charts,
            "subscription": user_profile.subscription_plan,  # 👈 Ajout
        })


def is_admin(user):
    return user.is_superuser


@user_passes_test(is_admin)
def upload_excel(request):
    return HttpResponse(
        "<h2>Upload Excel</h2><p>Formulaire d’upload de fichier Excel réservé à l’administrateur.</p>"
    )


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')  # redirige vers le tableau de bord
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


def home(request):
    return render(request, "home.html")


from django.contrib.auth import logout


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
                            "indexes":
                            Index.objects.all(),
                            "error":
                            "Vous avez atteint la limite de modifications."
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
