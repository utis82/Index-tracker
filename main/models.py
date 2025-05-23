from django.db import models
from django.contrib.auth.models import User

# Ce modèle représente un index (exemple : "CUIVRE - LME", "ALUMINIUM - LME", etc.)
class Index(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# Ce modèle représente une valeur d’un index à une certaine date
class IndexValue(models.Model):
    index = models.ForeignKey(
        Index,
        on_delete=models.CASCADE,
        related_name='values'
    )
    date = models.DateField()
    value = models.FloatField()

    def __str__(self):
        return f"{self.index.name} - {self.date}: {self.value}"


# Ce modèle représente des infos supplémentaires liées à l'utilisateur
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    PLAN_CHOICES = [
        ('free', 'Gratuit'),
        ('pack_5', 'Pack 5 index'),
        ('pack_10', 'Pack 10 index'),
        ('premium', 'Premium'),
    ]
    subscription_plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default='free'
    )

    favorite_indexes = models.ManyToManyField(Index, blank=True)

    # Champs pour gérer l’index principal
    primary_index = models.ForeignKey(
        Index,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='users_with_primary_index'
    )
    primary_index_change_count = models.PositiveIntegerField(default=0)

    # Méthodes utilitaires
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
