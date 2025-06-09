# main/utils.py
from collections import defaultdict
from .models import IndexValue

def get_user_index_data(user):
    """
    Récupère toutes les valeurs mensuelles des index favoris de l'utilisateur,
    sous forme de dictionnaire : { index_id: { date: value } }
    """
    index_ids = user.userprofile.favorite_indexes.values_list('id', flat=True)
    index_values = IndexValue.objects.filter(index_id__in=index_ids)

    data_by_index = defaultdict(dict)  # {index_id: {date: value}}

    for val in index_values:
        date = val.date.replace(day=1)  # standardiser au 1er du mois
        data_by_index[val.index_id][date] = val.value

    return data_by_index
