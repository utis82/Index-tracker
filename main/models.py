from django.db import models
from django.contrib.auth.models import User

# Ce modèle représente un index (exemple : "CUIVRE - LME", "ALUMINIUM - LME", etc.)
class Index(models.Model):
    name = models.CharField(max_length=100)  # Le nom de l'index (chaine de caractères limitée à 100 caractères)

    def __str__(self):
        return self.name  # Ce que Django affiche dans l’interface admin ou en console (affiche le nom)

# Ce modèle représente une valeur d’un index à une certaine date (ex : "CUIVRE - LME" le 01/01/2024 → 8400)
class IndexValue(models.Model):
    index = models.ForeignKey(
        Index,                      # Référence à un objet de type Index (clé étrangère)
        on_delete=models.CASCADE,  # Si l’index est supprimé, ses valeurs le sont aussi automatiquement
        related_name='values'      # Permet d’accéder facilement aux valeurs d’un index (ex : mon_index.values.all())
    )
    date = models.DateField()      # La date à laquelle la valeur de l’index a été enregistrée
    value = models.FloatField()    # La valeur numérique de l’index ce jour-là (ex : 8400.5)

    def __str__(self):
        # Affiche par exemple : "CUIVRE - LME - 2024-01-01: 8400.5"
        return f"{self.index.name} - {self.date}: {self.value}"

# Ce modèle représente des infos supplémentaires liées à l'utilisateur
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    subscription_valid = models.BooleanField(default=False)
    favorite_indexes = models.ManyToManyField(Index, blank=True)

    def __str__(self):
        return f"Profil de {self.user.username}"
