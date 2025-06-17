from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
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
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='parts')
    name = models.CharField(max_length=100)
    reference_date = models.DateField()
    reference_price = models.FloatField("Prix de référence (€)", help_text="Prix à la date de référence")

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
    part = models.ForeignKey(Part, null=True, blank=True, on_delete=models.CASCADE)
    value = models.FloatField()
    date = models.DateField()

    def __str__(self):
        return f"{self.index.name} - {self.date}: {self.value}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    PLAN_CHOICES = [
        ('free', 'Gratuit'),
        ('pack_5', 'Pack 5 index'),
        ('pack_10', 'Pack 10 index'),
        ('premium', 'Premium'),
    ]
    subscription_plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    favorite_indexes = models.ManyToManyField(Index, blank=True)
    primary_index = models.ForeignKey(Index, null=True, blank=True, on_delete=models.SET_NULL, related_name='users_with_primary_index')
    primary_index_change_count = models.PositiveIntegerField(default=0)

    def index_limit(self):
        return {
            'free': 1,
            'pack_5': 5,
            'pack_10': 10,
            'premium': float('inf')
        }[self.subscription_plan]

    def change_limit(self):
        return {
            'free': 3,
            'pack_5': 5,
            'pack_10': 10,
            'premium': float('inf')
        }[self.subscription_plan]

    def can_add_favorite(self):
        return self.favorite_indexes.count() < self.index_limit()

    def can_modify_favorites(self):
        return self.primary_index_change_count < self.change_limit()

# 🧩 Modèle Slice
class Slice(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name='slices')
    reference_date = models.DateField("Date de référence", null=True, blank=True)
    COMPONENT_TYPE_CHOICES = [
        ('fixed', 'Fixe (non indexé)'),
        ('indexed', 'Indexé')
    ]
    component_type = models.CharField(max_length=10, choices=COMPONENT_TYPE_CHOICES)
    percentage = models.FloatField(null=True, blank=True)
    fixed_amount = models.FloatField(null=True, blank=True)
    index = models.ForeignKey(Index, on_delete=models.SET_NULL, null=True, blank=True)
    label = models.CharField(max_length=100, help_text="Nom de la tranche (ex: énergie, transport...)")

    def __str__(self):
        return f"🔸 {self.label} ({self.part.name})"