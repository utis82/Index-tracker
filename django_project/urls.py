# django_project/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  # ← Garde-la ici
    path('', include('main.urls')),   # ← Et tout ton app ici
]
