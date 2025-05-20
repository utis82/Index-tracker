# main/urls.py
from django.urls import path
from main.views.base_views import (
    home,
    login_view,
    dashboard,
    register_view,
    upload_excel,
    logout_view,
    search_index,
)
from main.views.index_views import (import_excel_view, liste_index_view)
from main.views.chart_views import index_viewer

from main.views.user_views import toggle_favorite

app_name = 'main'

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('dashboard/', dashboard, name='dashboard'),
    path('upload/', upload_excel, name='upload'),
    path('index/import-excel/', import_excel_view, name='index_import_excel'),
    path('liste-index/', liste_index_view, name='liste_index'),
    path('logout/', logout_view, name='logout'),
    path('search-index/', search_index, name='search_index'),
    path('index-viewer/<int:index_id>/', index_viewer, name='index_viewer'),
    path('toggle-favorite/<int:index_id>/',
         toggle_favorite,
         name='toggle_favorite'),
]

#path('index-viewer/', index_viewer_view, name='index_viewer'),
