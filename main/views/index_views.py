from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from main.models import Index, IndexValue
from django.utils.dateformat import format as date_format


@login_required
def liste_index_view(request):
    """Vue pour afficher la liste des index avec leurs valeurs récentes"""
    indexes = Index.objects.all()
    enriched_indexes = []

    for index in indexes:
        values = IndexValue.objects.filter(index=index).order_by('-date')
        if values.exists():
            latest_value = values.first()
            recent_values = list(values.order_by('date'))[-30:]
            value_data = {
                'date': latest_value.date.strftime("%d/%m/%Y"),
                'value': latest_value.value,
                'unit': index.unit,
                'dates': [date_format(v.date, "Y-m-d") for v in recent_values],
                'values': [v.value for v in recent_values],
            }
        else:
            value_data = {
                'date': "—",
                'value': "—",
                'unit': index.unit or "—",
                'history': [],
            }

        enriched_indexes.append({'index': index, 'latest': value_data})

    # Préparer le contexte
    context = {
        'indexes': enriched_indexes,
    }

    # Ajouter les favoris si l'utilisateur est connecté et a un profil
    if request.user.is_authenticated:
        try:
            context['favorites'] = request.user.userprofile.favorite_indexes.all()
        except AttributeError:
            context['favorites'] = []
    else:
        context['favorites'] = []

    return render(request, 'liste_index.html', context)