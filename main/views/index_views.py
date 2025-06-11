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

            # ✅ détecter les colonnes de dates (colonnes de type datetime)
            date_columns = [col for col in df.columns if isinstance(col, datetime)]

            for _, row in df.iterrows():
                index_name = row["Designation"]
                if pd.isna(index_name):
                    continue

                # ✅ Lire les champs associés
                unit = row["Unit"] if "Unit" in df.columns and not pd.isna(row["Unit"]) else "€"
                category = row["category"] if "category" in df.columns and not pd.isna(row["category"]) else "Autre"

                # ✅ Crée ou met à jour l’index
                index_obj, _ = Index.objects.update_or_create(
                    name=index_name,
                    defaults={"unit": unit, "category": category}
                )

                for col in date_columns:
                    raw_value = row[col]
                    if pd.isna(raw_value) or str(raw_value).strip() == "-":
                        continue

                    try:
                        float_value = float(raw_value)
                    except ValueError:
                        continue

                    IndexValue.objects.update_or_create(
                        index=index_obj,
                        date=col,
                        defaults={"value": float_value}
                    )

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

