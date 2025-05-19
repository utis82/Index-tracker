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


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")
        else:
            return render(request, "login.html",
                          {"error": "Identifiants invalides."})

    return render(request, "login.html")


@login_required
def dashboard(request):
    index_list = Index.objects.all().order_by("name")
    return render(request, "dashboard.html")



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

