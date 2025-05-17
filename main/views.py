from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm

def home(request):
    return HttpResponse("<h1>Bienvenue sur la page d'accueil</h1><p>Ceci est une plateforme de suivi des index de matières premières. Connectez-vous pour accéder à votre dashboard.</p>")

def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")
        else:
            return render(request, "login.html", {"error": "Identifiants invalides."})

    return render(request, "login.html")

@login_required
def dashboard(request):
    return HttpResponse(f"<h2>Dashboard</h2><p>Bienvenue {request.user.username} !</p>")

def is_admin(user):
    return user.is_superuser

@user_passes_test(is_admin)
def upload_excel(request):
    return HttpResponse("<h2>Upload Excel</h2><p>Formulaire d’upload de fichier Excel réservé à l’administrateur.</p>")

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
