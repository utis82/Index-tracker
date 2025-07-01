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


# 🧱 Modèle Part avec prix de référence
class Part(models.Model):
    product = models.ForeignKey(Product,
                                on_delete=models.CASCADE,
                                related_name='parts')
    name = models.CharField(max_length=100)
    reference_date = models.DateField()
    reference_price = models.FloatField(
        "Prix de référence (€)", help_text="Prix à la date de référence")

    def __str__(self):
        return f"🔹 {self.name} ({self.product.name}) - {self.reference_price}€"


class Index(models.Model):
    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=20, default="€/t")
    category = models.CharField(max_length=50, default="Autre")

    def __str__(self):
        return self.name


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

        # Dans votre models.py, remplacez la classe UserProfile par :


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
    # NOUVEAU : Compteur spécifique aux favoris
    favorite_changes_count = models.PositiveIntegerField(default=0)

    # SUPPRIMÉ : primary_index et primary_index_change_count

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


# 🧩 Modèle Slice
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
