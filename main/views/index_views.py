from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin.views.decorators import staff_member_required
# import pandas as pd  # ← Remplacé par openpyxl
import openpyxl  # ← Alternative légère à pandas pour Excel
from datetime import datetime
from main.models import Index, IndexValue


from io import BytesIO
from django.utils.timezone import localtime
from django.utils.dateformat import format as date_format


@login_required
@user_passes_test(lambda u: u.is_superuser)
def import_excel_view(request):
    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")

        if not excel_file:
            return HttpResponse("❌ Aucun fichier n'a été envoyé.")

        try:
            # ✅ Utiliser openpyxl au lieu de pandas
            workbook = openpyxl.load_workbook(BytesIO(excel_file.read()))

            # Vérifier si la feuille "1. BDD" existe
            if "1. BDD" not in workbook.sheetnames:
                return HttpResponse("❌ Feuille '1. BDD' non trouvée dans l'Excel.")

            worksheet = workbook["1. BDD"]

            # Lire la première ligne pour les en-têtes
            headers = []
            for cell in worksheet[1]:
                if cell.value:
                    headers.append(cell.value)
                else:
                    headers.append("")

            print("🔍 Colonnes détectées :", headers)

            if "Designation" not in headers:
                return HttpResponse("❌ Colonne 'Designation' manquante dans l'Excel.")

            # Trouver les indices des colonnes importantes
            designation_col = headers.index("Designation")
            unit_col = headers.index("Unit") if "Unit" in headers else None
            category_col = headers.index("category") if "category" in headers else None

            # Identifier les colonnes de dates (à partir de la colonne 3 généralement)
            date_columns = []
            for i, header in enumerate(headers):
                if isinstance(header, datetime) or (isinstance(header, str) and len(header) > 8):
                    try:
                        # Essayer de parser comme date
                        if isinstance(header, str):
                            parsed_date = datetime.strptime(header, "%Y-%m-%d")
                        else:
                            parsed_date = header
                        date_columns.append((i, parsed_date))
                    except:
                        continue

            # Traiter chaque ligne (à partir de la ligne 2)
            for row_num in range(2, worksheet.max_row + 1):
                row = list(worksheet[row_num])

                # Lire le nom de l'index
                if designation_col < len(row) and row[designation_col].value:
                    index_name = str(row[designation_col].value).strip()
                else:
                    continue

                if not index_name:
                    continue

                # Lire les champs associés
                unit = "€"  # Valeur par défaut
                if unit_col is not None and unit_col < len(row) and row[unit_col].value:
                    unit = str(row[unit_col].value)

                category = "Autre"  # Valeur par défaut
                if category_col is not None and category_col < len(row) and row[category_col].value:
                    category = str(row[category_col].value)

                # ✅ Créer ou mettre à jour l'index
                index_obj, created = Index.objects.update_or_create(
                    name=index_name,
                    defaults={
                        "unit": unit,
                        "category": category
                    }
                )

                # Traiter les valeurs pour chaque date
                for col_index, date_value in date_columns:
                    if col_index < len(row) and row[col_index].value is not None:
                        raw_value = row[col_index].value

                        # Ignorer les cellules vides ou avec "-"
                        if raw_value is None or str(raw_value).strip() in ["", "-"]:
                            continue

                        try:
                            float_value = float(raw_value)
                        except (ValueError, TypeError):
                            continue

                        # Créer ou mettre à jour la valeur
                        IndexValue.objects.update_or_create(
                            index=index_obj,
                            date=date_value.date(),
                            defaults={"value": float_value}
                        )

            return HttpResponse("✅ Importation terminée avec succès.")

        except openpyxl.utils.exceptions.InvalidFileException:
            return HttpResponse("❌ Fichier Excel invalide ou corrompu.")
        except Exception as e:
            return HttpResponse(f"❌ Erreur lors du traitement du fichier : {str(e)}")

    return render(request, "admin/import_excel.html")

@login_required
def liste_index_view(request):
    indexes = Index.objects.all()
    enriched_indexes = []

    for index in indexes:
        values = IndexValue.objects.filter(index=index).order_by('-date')
        if values.exists():
            latest_value = values.first()
            recent_values = list(values.order_by('date'))[-30:]
            value_data = {
                'date': latest_value.date.strftime("%d/%m/%Y"),
                'value': latest_value.value,
                'unit': index.unit,
                'dates': [date_format(v.date, "Y-m-d") for v in recent_values],
                'values': [v.value for v in recent_values],
            }
        else:
            value_data = {
                'date': "—",
                'value': "—",
                'unit': index.unit or "—",
                'history': [],
            }

        enriched_indexes.append({'index': index, 'latest': value_data})

    return render(
        request, 'liste_index.html', {
            'indexes': enriched_indexes,
            'favorites': request.user.userprofile.favorite_indexes.all()
        })