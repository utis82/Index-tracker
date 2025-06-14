from django.core.management.base import BaseCommand
from main.models import IndexValue, Part

class Command(BaseCommand):
    help = "Assigne un Part par défaut aux IndexValue qui n'en ont pas."

    def handle(self, *args, **kwargs):
        default_part = Part.objects.first()

        if not default_part:
            self.stdout.write(self.style.ERROR("❌ Aucun Part trouvé en base."))
            return

        count = 0
        for iv in IndexValue.objects.filter(part__isnull=True):
            iv.part = default_part
            iv.save()
            count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {count} IndexValue mis à jour avec le Part ID {default_part.id} ({default_part.name})"))
