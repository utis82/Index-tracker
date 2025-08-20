from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from main.models import Index, IndexValue
from django.utils.dateformat import format as date_format
from django.db.models import Q
from django.http import JsonResponse

@login_required
def liste_index_view(request):
    """Vue améliorée pour afficher la liste des index avec recherche et filtres"""

    # Récupération des paramètres de filtrage et recherche
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '')
    sort_by = request.GET.get('sort', 'name-asc')

    # Query de base - tous les index
    indexes = Index.objects.all()

    # Application du filtre de recherche textuelle
    if search_query:
        indexes = indexes.filter(
            Q(name__icontains=search_query) |
            Q(category__icontains=search_query)
        )

    # Application du filtre par catégorie
    if category_filter:
        indexes = indexes.filter(category=category_filter)

    # Application du tri
    if sort_by == 'name-asc':
        indexes = indexes.order_by('name')
    elif sort_by == 'name-desc':
        indexes = indexes.order_by('-name')
    elif sort_by == 'category':
        indexes = indexes.order_by('category', 'name')
    elif sort_by == 'latest-update':
        # Tri par dernière mise à jour (nécessite une sous-requête)
        indexes = indexes.order_by('-updated_at') if hasattr(Index, 'updated_at') else indexes.order_by('name')

    # Enrichissement des données comme avant
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
                'dates': [],
                'values': [],
            }
        enriched_indexes.append({'index': index, 'latest': value_data})

    # Récupération de toutes les catégories disponibles pour le filtre
    all_categories = Index.objects.values_list('category', flat=True).distinct().order_by('category')
    categories = [cat for cat in all_categories if cat and cat.strip()]  # Enlever les valeurs vides

    # Si c'est une requête AJAX (pour le filtrage en temps réel)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Retourner seulement les données filtrées en JSON
        filtered_data = []
        for entry in enriched_indexes:
            index = entry['index']
            latest = entry['latest']
            filtered_data.append({
                'id': index.id,
                'name': index.name,
                'category': index.category,
                'latest_value': latest['value'],
                'latest_date': latest['date'],
                'unit': latest['unit'],
                'dates': latest['dates'],
                'values': latest['values'],
                'url': f"/index/{index.id}/",  # Ajustez selon votre URL pattern
            })

        return JsonResponse({
            'indexes': filtered_data,
            'total_count': len(filtered_data)
        })

    # Préparer le contexte pour le rendu normal
    context = {
        'indexes': enriched_indexes,
        'categories': categories,
        'current_search': search_query,
        'current_category': category_filter,
        'current_sort': sort_by,
        'total_count': len(enriched_indexes),
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