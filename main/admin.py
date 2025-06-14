from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from main.models import Product, Part, Slice, Index, IndexValue, UserProfile
import openpyxl  # pour lecture de fichiers Excel (.xlsx)


# --- Inlines ---
class PartInline(admin.TabularInline):
    model = Part
    extra = 0
    fields = ("name",)


class SliceInline(admin.TabularInline):
    model = Slice
    extra = 0
    fields = ("label",)


class IndexValueInline(admin.TabularInline):
    model = IndexValue
    extra = 0
    fields = ("index", "value")


# --- Admin Product ---
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    inlines = [PartInline]


# --- Admin Part ---
@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("name", "product")
    search_fields = ("name", "product__name")
    list_select_related = ("product",)
    inlines = [SliceInline, IndexValueInline]


# --- Admin Slice ---
@admin.register(Slice)
class SliceAdmin(admin.ModelAdmin):
    list_display = ("label", "part")
    search_fields = ("label", "part__name")
    list_select_related = ("part",)


# --- Admin Index avec bouton Import ---
@admin.register(Index)
class IndexAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    change_list_template = "admin/index_changelist.html"  # surcharge du template admin pour bouton

    actions = ["import_from_excel"]  # action dans le menu déroulant admin

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'import-excel/',
                self.admin_site.admin_view(self.redirect_to_import),
                name='index_import_excel_admin'
            )
        ]
        return custom_urls + urls

    def redirect_to_import(self, request):
        # redirige vers la vue déjà existante de l'import
        return redirect('main:index_import_excel')

    def import_from_excel(self, request, queryset):
        try:
            workbook = openpyxl.load_workbook("import_data.xlsx")
            sheet = workbook.active
            for row in sheet.iter_rows(min_row=2, values_only=True):
                index_name, part_id, value = row[0], row[1], row[2]
                if not index_name or not part_id:
                    continue
                index_obj, _ = Index.objects.get_or_create(name=index_name)
                try:
                    part_obj = Part.objects.get(id=part_id)
                except Part.DoesNotExist:
                    continue
                IndexValue.objects.update_or_create(
                    part=part_obj, index=index_obj,
                    defaults={"value": value}
                )
            self.message_user(request, "Données Excel importées avec succès !", messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"Erreur lors de l'importation : {e}", messages.ERROR)

    import_from_excel.short_description = "Importer des données Excel"


# --- Admin UserProfile ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user",)
    search_fields = ("user__username", "user__email")
