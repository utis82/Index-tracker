# main/urls.py
from django.urls import path
from main.views.base_views import (home, login_view, dashboard, register_view,
                                   upload_excel, logout_view, search_index,
                                   choose_primary_index)
from main.views.index_views import import_excel_view, liste_index_view
from main.views.chart_views import index_viewer
from main.views.user_views import toggle_favorite
from main.views.prix_indexes_views import prix_indexes_view, delete_structure
from main.views.prix_indexes_views import prix_indexes_view, delete_structure, get_structure_data

app_name = 'main'

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('dashboard/', dashboard, name='dashboard'),  # ✅ corrigé ici
    path('upload/', upload_excel, name='upload'),
    path('index/import-excel/', import_excel_view, name='index_import_excel'),
    path('liste-index/', liste_index_view, name='liste_index'),
    path('logout/', logout_view, name='logout'),
    path('search-index/', search_index, name='search_index'),
    path('index-viewer/<int:index_id>/', index_viewer, name='index_viewer'),
    path('index-viewer/', index_viewer, name='index_viewer_home'),
    path('toggle-favorite/<int:index_id>/',
         toggle_favorite,
         name='toggle_favorite'),
    path('choose-primary-index/',
         choose_primary_index,
         name='choose_primary_index'),
    path('prix-indexes/', prix_indexes_view, name='prix_indexes'),
    path('delete-structure/<int:pk>/',
         delete_structure,
         name='delete_structure'),
     path('structure-data/<int:pk>/', get_structure_data, name='get_structure_data'),

]
