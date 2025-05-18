from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin.views.decorators import staff_member_required
import pandas as pd
from datetime import datetime
from .models import Index, IndexValue
import matplotlib.pyplot as plt
import base64
from io import BytesIO


@login_required
@user_passes_test(lambda u: u.is_superuser)
def import_excel_view(request):
    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")

        if not excel_file:
            return HttpResponse("❌ Aucun fichier n’a été envoyé.")

        try:
            # Lire le fichier avec pandas
            df = pd.read_excel(BytesIO(excel_file.read()), sheet_name="1. BDD")

            print("🔍 Colonnes détectées :", df.columns.tolist())

            if "Designation" not in df.columns:
                return HttpResponse(
                    "❌ Colonne 'Designation' manquante dans l'Excel.")

            # Pour chaque ligne
            for _, row in df.iterrows():
                index_name = row["Designation"]
                if pd.isna(index_name):
                    continue

                index_obj, _ = Index.objects.get_or_create(name=index_name)

                # Parcours des colonnes mois (toutes sauf la première colonne)
                for col in df.columns[1:]:
                    raw_value = row[col]

                    # On ignore les vides, les NaN, ou les tirets "-"
                    if pd.isna(raw_value) or str(raw_value).strip() == "-":
                        continue

                    try:
                        # On s'assure que la valeur peut être convertie en float
                        float_value = float(raw_value)
                    except ValueError:
                        print(
                            f"⚠️ Valeur non convertible en float : {raw_value}"
                        )
                        continue

                    # Traitement de la date
                    try:
                        date_obj = datetime.strptime(str(col), "%m/%Y")
                    except ValueError:
                        try:
                            date_obj = datetime.strptime(
                                str(col).split()[0], "%Y-%m-%d")
                        except ValueError:
                            print(f"❌ Mauvais format de date : {col}")
                            continue

                    IndexValue.objects.create(index=index_obj,
                                              date=date_obj,
                                              value=raw_value)
                    print(
                        f"💾 Valeur enregistrée pour {index_name} le {date_obj} → {raw_value}"
                    )

            return HttpResponse("✅ Importation terminée avec succès.")

        except Exception as e:
            return HttpResponse(
                f"❌ Erreur lors du traitement du fichier : {str(e)}")

    return render(request, "admin/import_excel.html")


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


@login_required
def index_viewer_view(request):
    selected_index_id = request.GET.get("index_id")
    chart = None

    # Récupérer tous les index pour la liste déroulante
    all_indexes = Index.objects.all().order_by("name")

    if selected_index_id:
        try:
            index = Index.objects.get(id=selected_index_id)
            values = IndexValue.objects.filter(index=index).order_by("date")

            if values.exists():
                dates = [v.date for v in values]
                val = [v.value for v in values]

                # Création du graphique matplotlib
                fig, ax = plt.subplots(figsize=(8, 4))
                ax.plot(dates, val, marker='o')
                ax.set_title(index.name)
                ax.set_xlabel("Date")
                ax.set_ylabel("Valeur")
                ax.grid(True)

                # Sauvegarde dans un buffer mémoire
                buffer = BytesIO()
                plt.tight_layout()
                fig.autofmt_xdate()
                plt.savefig(buffer, format="png")
                buffer.seek(0)
                image_png = buffer.getvalue()
                buffer.close()

                # Encodage base64 pour affichage HTML
                chart = base64.b64encode(image_png).decode("utf-8")
                plt.close(fig)

        except Index.DoesNotExist:
            chart = None

    return render(
        request, "index_viewer.html", {
            "all_indexes": all_indexes,
            "chart": chart,
            "selected_index_id": selected_index_id
        })


def home(request):
    return HttpResponse("<h1>Bienvenue sur l’accueil de l’application</h1>")
