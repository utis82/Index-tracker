from django.db import models
from django.contrib.auth.models import User
import random
import string
from datetime import datetime, timedelta
from django.utils import timezone


class Product(models.Model):
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='products')
    name = models.CharField(max_length=100)
    reference_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def total_reference_price(self):
        """Calcule le prix de référence total du produit (somme des pièces)"""
        return sum(part.reference_price for part in self.parts.all())

    def __str__(self):
        return f"📦 {self.name}"


class Part(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='parts',
        null=True,  # ← AJOUTEZ cette ligne
        blank=True)  # ← AJOUTEZ cette ligne
    user = models.ForeignKey(
        User, on_delete=models.CASCADE)  # ← AJOUTEZ cette ligne complète
    name = models.CharField(max_length=100)
    reference_date = models.DateField()
    reference_price = models.FloatField(
        "Prix de référence (€)", help_text="Prix à la date de référence")

    def __str__(self):
        product_name = self.product.name if self.product else "Part indépendante"
        return f"🔹 {self.name} ({product_name}) - {self.reference_price}€"


class Index(models.Model):
    # 🚨 CORRECTION : Catégories avec des choices prédéfinies
    CATEGORY_CHOICES = [
        ('batiment', 'Bâtiment et Construction'),
        ('energie', 'Énergie'),
        ('matiere_premiere', 'Matières Premières'),
        ('transport', 'Transport et Logistique'),
        ('main_oeuvre', 'Main d\'œuvre'),
        ('equipement', 'Équipement et Machines'),
        ('service', 'Services'),
        ('agriculture', 'Agriculture'),
        ('metaux', 'Métaux'),
        ('chimie', 'Chimie et Pétrochimie'),
        ('textile', 'Textile'),
        ('alimentaire', 'Industrie Alimentaire'),
        ('Inflation', 'Inflation'),
        ('autre', 'Autre'),
    ]

    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=20, default="€/t")
    category = models.CharField(max_length=50,
                                choices=CATEGORY_CHOICES,
                                default='autre',
                                help_text="Catégorie de l'index")

    def __str__(self):
        return self.name

    def get_category_display_with_emoji(self):
        """Retourne la catégorie avec un emoji pour l'affichage"""
        emoji_map = {
            'batiment': '🏗️',
            'energie': '⚡',
            'matiere_premiere': '🏭',
            'transport': '🚛',
            'main_oeuvre': '👷',
            'equipement': '⚙️',
            'service': '🔧',
            'agriculture': '🌾',
            'metaux': '🔩',
            'chimie': '🧪',
            'textile': '🧵',
            'alimentaire': '🍞',
            'autre': '📋',
        }
        emoji = emoji_map.get(self.category, '📋')
        return f"{emoji} {self.get_category_display()}"


class IndexValue(models.Model):
    index = models.ForeignKey(Index, on_delete=models.CASCADE)
    part = models.ForeignKey(Part,
                             null=True,
                             blank=True,
                             on_delete=models.CASCADE)
    value = models.FloatField()
    date = models.DateField()

    def __str__(self):
        return f"{self.index.name} - {self.date}: {self.value}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('5_index', '5 Index'),
        ('10_index', '10 Index'),
        ('premium', 'Premium'),
    ]
    subscription_plan = models.CharField(max_length=20,
                                         choices=PLAN_CHOICES,
                                         default='free')
    favorite_indexes = models.ManyToManyField(Index, blank=True)
    favorite_changes_count = models.PositiveIntegerField(default=0)

    def index_limit(self):
        return {
            'free': 1,
            '5_index': 5,
            '10_index': 10,
            'premium': float('inf')
        }[self.subscription_plan]

    def change_limit(self):
        return {
            'free': 4,
            '5_index': 6,
            '10_index': 11,
            'premium': float('inf')
        }[self.subscription_plan]

    def can_add_favorite(self):
        return self.favorite_indexes.count() < self.index_limit()

    def can_modify_favorites(self):
        return self.favorite_changes_count < self.change_limit()


class Slice(models.Model):
    part = models.ForeignKey(Part,
                             on_delete=models.CASCADE,
                             related_name='slices')
    reference_date = models.DateField("Date de référence",
                                      null=True,
                                      blank=True)
    COMPONENT_TYPE_CHOICES = [('fixed', 'Fixe (non indexé)'),
                              ('indexed', 'Indexé')]
    component_type = models.CharField(max_length=10,
                                      choices=COMPONENT_TYPE_CHOICES)
    percentage = models.FloatField(null=True, blank=True)
    fixed_amount = models.FloatField(null=True, blank=True)
    index = models.ForeignKey(Index,
                              on_delete=models.SET_NULL,
                              null=True,
                              blank=True)
    label = models.CharField(
        max_length=100,
        help_text="Nom de la tranche (ex: énergie, transport...)")

    def __str__(self):
        return f"🔸 {self.label} ({self.part.name})"


class EmailVerification(models.Model):
    """Modèle pour stocker les codes de vérification email"""
    user = models.OneToOneField(User,
                                on_delete=models.CASCADE,
                                related_name='email_verification')
    verification_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Vérification {self.user.username} - {self.verification_code}"

    @classmethod
    def generate_code(cls):
        """Génère un code à 6 chiffres"""
        return ''.join(random.choices(string.digits, k=6))

    def is_expired(self):
        """Vérifie si le code a expiré (15 minutes)"""
        expiry_time = self.created_at + timedelta(minutes=15)
        return timezone.now() > expiry_time

    def save(self, *args, **kwargs):
        if not self.verification_code:
            self.verification_code = self.generate_code()
        super().save(*args, **kwargs)


# 🚨 FONCTION UTILITAIRE POUR LE MAPPING DES CATÉGORIES EXCEL
def map_excel_category_to_django(excel_category):
    """
    Mappe les catégories du fichier Excel vers les catégories Django
    """
    if not excel_category:
        return 'autre'

    # Normaliser la catégorie Excel (minuscules, sans accents, etc.)
    category = excel_category.lower().strip()

    # 🚨 MAPPING EXACT POUR VOTRE FICHIER EXCEL
    mapping = {
        # Catégories exactes de votre fichier Excel
        'raw material': 'matiere_premiere',
        'energy': 'energie',
        'labour cost': 'main_oeuvre',
        'logistic': 'transport',
        'inflation': 'Inflation',

        # Variantes (rétrocompatibilité)
        'raw materials': 'matiere_premiere',
        'labour': 'main_oeuvre',
        'labor': 'main_oeuvre',
        'labor cost': 'main_oeuvre',
        'logistics': 'transport',
        'logistique': 'transport',

        # Autres mappings existants
        'bâtiment': 'batiment',
        'batiment': 'batiment',
        'construction': 'batiment',
        'building': 'batiment',
        'énergie': 'energie',
        'energie': 'energie',
        'électricité': 'energie',
        'gaz': 'energie',
        'transport': 'transport',
        'main d\'œuvre': 'main_oeuvre',
        'main d\'oeuvre': 'main_oeuvre',
        'équipement': 'equipement',
        'equipement': 'equipement',
        'service': 'service',
        'services': 'service',
        'agriculture': 'agriculture',
        'métaux': 'metaux',
        'metaux': 'metaux',
        'acier': 'metaux',
        'chimie': 'chimie',
        'textile': 'textile',
        'alimentaire': 'alimentaire',
        'autre': 'autre',
        'autres': 'autre',
    }

    return mapping.get(category, 'autre')
