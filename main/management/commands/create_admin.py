# Crée ce fichier : main/management/commands/create_admin.py

import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Crée un superutilisateur automatiquement'

    def handle(self, *args, **options):
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin',
                email='***REMOVED***', 
                password='***REMOVED***'
            )
            self.stdout.write(
                self.style.SUCCESS('🔑 Superutilisateur créé avec succès!')
            )
            self.stdout.write('📧 Username: admin')
            self.stdout.write('🔐 Password: ***REMOVED***')
        else:
            self.stdout.write(
                self.style.WARNING('👤 Un superutilisateur existe déjà')
            )