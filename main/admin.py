from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
from .models import UserProfile
from .models import IndexedPriceStructure, StructureComponent

import pandas as pd

from .models import Index, IndexValue

# Enregistrement des modèles dans l'admin classique
admin.site.register(IndexValue)


@admin.register(Index)
class IndexAdmin(admin.ModelAdmin):
    search_fields = ("name",)  # ✅ Ajoute cette ligne
    change_list_template = "admin/index_changelist.html"

    def get_urls(self):
        # On ajoute une URL personnalisée qui sera utilisée pour uploader le fichier Excel
        urls = super().get_urls()
        custom_urls = [path("import-excel/", self.import_excel_view)]
        return custom_urls + urls

    def import_excel_view(self, request):
        if request.method == "POST" and request.FILES.get("excel_file"):
            excel_file = request.FILES["excel_file"]

            try:
                # Lecture du fichier Excel (onglet BDD)
                df = pd.read_excel(excel_file, sheet_name="BDD")

                # Parcours du dataframe pour insérer les données
                for index, row in df.iterrows():
                    index_name = row["Nom Index"]
                    date = row["Date"]
                    value = row["Valeur"]

                    if pd.isna(index_name) or pd.isna(date) or pd.isna(value):
                        continue  # Ignore les lignes incomplètes

                    # Récupère ou crée l'index
                    index_obj, _ = Index.objects.get_or_create(name=index_name)

                    # Ajoute la valeur correspondante
                    IndexValue.objects.create(index=index_obj,
                                              date=date,
                                              value=value)

                messages.success(request, "Importation réussie ✔")
            except Exception as e:
                messages.error(request, f"Erreur lors de l'import : {e}")

            return HttpResponseRedirect("../")

        return render(request, "admin/import_excel.html")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription_plan')

class StructureComponentInline(admin.TabularInline):
    model = StructureComponent
    extra = 1  # Nombre de lignes vierges à afficher
    fields = ("label", "component_type", "percentage", "fixed_amount", "index")
    autocomplete_fields = ("index",)


@admin.register(IndexedPriceStructure)
class IndexedPriceStructureAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "base_price", "reference_date", "created_at")
    list_filter = ("user", "reference_date")
    search_fields = ("name", "user__username")
    date_hierarchy = "created_at"
    inlines = [StructureComponentInline]