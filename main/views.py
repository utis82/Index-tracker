from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin.views.decorators import staff_member_required
import pandas as pd
from io import BytesIO
from datetime import datetime
from .models import Index, IndexValue

@login_required
@user_passes_test(lambda u: u.is_superuser)
def import_excel_view(request):
    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")

        if not excel_file:
            return HttpResponse("❌ Aucun fichier n’a été envoyé.")

        try:
            # On lit le fichier en mémoire avec pandas
            df = pd.read_excel(BytesIO(excel_file.read()), sheet_name="1. BDD")

            # Vérification présence de la colonne "Designation"
            if "Designation"not in df.columns:
                return HttpResponse("❌ Colonne 'Nom Index' manquante dans l'Excel.")

            # Pour chaque ligne du fichier Excel
            for _, row in df.iterrows():
                index_name = row["Designation"]
                if pd.isna(index_name):
                    continue  # Ignore les lignes sans nom

                # On crée ou récupère l'index en base
                index_obj, _ = Index.objects.get_or_create(name=index_name)

                # Parcours des colonnes mois (toutes sauf la première colonne)
                for col in df.columns[1:]:
                    raw_value = row[col]
                    if pd.isna(raw_value):
                        continue  # Ignore les cellules vides

                    try:
                        # Convertit le nom de colonne en date (format: mm/yyyy ou mm/yy)
                        date_obj = datetime.strptime(str(col), "%m/%Y")
                    except ValueError:
                        continue  # Ignore les colonnes non date

                    # Crée une valeur liée à l'index
                    IndexValue.objects.create(
                        index=index_obj,
                        date=date_obj,
                        value=raw_value
                    )

            return HttpResponse("✅ Importation terminée avec succès.")

        except Exception as e:
            return HttpResponse(f"❌ Erreur lors du traitement du fichier : {str(e)}")

    # Affiche le formulaire si GET
    return render(request, "admin/import_excel.html")


def home(request):
    return HttpResponse(
        "<h1>Bienvenue sur la page d'accueil</h1><p>Ceci est une plateforme de suivi des index de matières premières. Connectez-vous pour accéder à votre dashboard.</p>"
    )


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
    return HttpResponse(
        f"<h2>Dashboard</h2><p>Bienvenue {request.user.username} !</p>")


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

@login_required
def liste_index_view(request):
    index_list = Index.objects.all().order_by("name")  # trié par nom
    return render(request, "liste_index.html", {"index_list": index_list})
