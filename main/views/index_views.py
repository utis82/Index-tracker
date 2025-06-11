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

@login_required
@user_passes_test(lambda u: u.is_superuser)
def import_excel_view(request):
    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")

        if not excel_file:
            return HttpResponse("❌ Aucun fichier n’a été envoyé.")

        try:
            df = pd.read_excel(BytesIO(excel_file.read()), sheet_name="1. BDD")
            print("🔍 Colonnes détectées :", df.columns.tolist())

            if "Designation" not in df.columns:
                return HttpResponse("❌ Colonne 'Designation' manquante dans l'Excel.")

            for _, row in df.iterrows():
                index_name = row["Designation"]
                if pd.isna(index_name):
                    continue

                # ✅ Lire l’unité si présente
                unit = row["Unit"] if "Unit" in df.columns and not pd.isna(row["Unit"]) else "€"


                # ✅ Crée ou met à jour l’index avec l’unité
                index_obj, _ = Index.objects.update_or_create(
                    name=index_name,
                    defaults={"unit": unit}
                )

                # 🔁 Parcours des colonnes de dates (tout sauf Designation et Unité)
                date_columns = [col for col in df.columns if isinstance(col, datetime)]
                for col in date_columns:


                    raw_value = row[col]
                    if pd.isna(raw_value) or str(raw_value).strip() == "-":
                        continue

                    try:
                        float_value = float(raw_value)
                    except ValueError:
                        print(f"⚠️ Valeur non convertible en float : {raw_value}")
                        continue

                    # ✅ Gestion flexible des formats de date
                    try:
                        date_obj = datetime.strptime(str(col), "%m/%Y")
                    except ValueError:
                        try:
                            date_obj = datetime.strptime(str(col).split()[0], "%Y-%m-%d")
                        except ValueError:
                            print(f"❌ Mauvais format de date : {col}")
                            continue

                    # ✅ Crée ou met à jour la valeur existante
                    IndexValue.objects.update_or_create(
                        index=index_obj,
                        date=date_obj,
                        defaults={"value": float_value}
                    )

                    print(f"💾 {index_name} | {date_obj.strftime('%Y-%m-%d')} → {float_value} ({unit})")

            return HttpResponse("✅ Importation terminée avec succès.")

        except Exception as e:
            return HttpResponse(f"❌ Erreur lors du traitement du fichier : {str(e)}")

    return render(request, "admin/import_excel.html")




@login_required
def liste_index_view(request):
    index_list = Index.objects.all().order_by("name")
    return render(request, "liste_index.html", {
        "index_list": index_list,     # pour la liste affichée
        "all_indexes": index_list     # pour la barre de recherche
    })

