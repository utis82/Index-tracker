# main/urls.py

from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_excel, name='upload'),
    path('index/import-excel/', views.import_excel_view, name='index_import_excel'),
    path('liste-index/', views.liste_index_view, name='liste_index'),
    path('index-viewer/', views.index_viewer_view, name='index_viewer'),

]
