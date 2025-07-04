from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from main.models import Product, Part, Slice, Index, IndexValue, UserProfile

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

# --- Admin Index avec bouton Import (NETTOYÉ) ---
@admin.register(Index)
class IndexAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "category")  # Ajout unit et category pour voir
    search_fields = ("name", "category")
    list_filter = ("category",)  # Filtre par catégorie
    change_list_template = "admin/index_changelist.html"

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
        """Redirige vers notre fonction d'import optimisée dans base_views.py"""
        return redirect('main:index_import_excel')

# --- Admin UserProfile ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "subscription_plan")
    search_fields = ("user__username", "user__email")
    list_filter = ("subscription_plan",)