# main/urls.py
from django.urls import path
from main.views.base_views import (
    home,
    login_view,
    dashboard,
    register_view,
    upload_excel,
    logout_view
)
from main.views.index_views import (
    import_excel_view,
    liste_index_view
)
from main.views.chart_views import index_viewer_view





app_name = 'main'

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('dashboard/', dashboard, name='dashboard'),
    path('upload/', upload_excel, name='upload'),
    path('index/import-excel/', import_excel_view, name='index_import_excel'),
    path('liste-index/', liste_index_view, name='liste_index'),
    path('index-viewer/', index_viewer_view, name='index_viewer'),
    path('logout/', logout_view, name='logout'),

]
