            # main/management/commands/create_admin.py - VERSION SÉCURISÉE

            import os
            from django.core.management.base import BaseCommand
            from django.contrib.auth.models import User

            class Command(BaseCommand):
                help = 'Crée un superutilisateur avec les variables d\'environnement'

                def handle(self, *args, **options):
                    # Lire depuis les variables d'environnement (SÉCURISÉ)
                    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
                    admin_email = os.environ.get('ADMIN_EMAIL', '***REMOVED***')
                    admin_password = os.environ.get('ADMIN_PASSWORD')

                    if not admin_password:
                        self.stdout.write(
                            self.style.ERROR('❌ Variable ADMIN_PASSWORD non définie !')
                        )
                        return

                    if not User.objects.filter(is_superuser=True).exists():
                        User.objects.create_superuser(
                            username=admin_username,
                            email=admin_email, 
                            password=admin_password
                        )
                        self.stdout.write(
                            self.style.SUCCESS('🔑 Superutilisateur créé avec succès!')
                        )
                        self.stdout.write(f'📧 Username: {admin_username}')
                        self.stdout.write(f'✉️ Email: {admin_email}')
                    else:
                        self.stdout.write(
                            self.style.WARNING('👤 Un superutilisateur existe déjà')
                        )