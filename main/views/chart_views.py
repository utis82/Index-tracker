from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from main.models import Index, IndexValue
from main.decorators import subscription_required
from django.core.serializers.json import DjangoJSONEncoder
from statistics import mean
from datetime import datetime
import json

@login_required
@subscription_required
def index_viewer(request, index_id=None):
    """
    Vue principale pour l'analyse d'index avec comparaison de deux périodes
    """
    user_profile = request.user.userprofile
    favorites = user_profile.favorite_indexes.all()

    # Récupération des index sélectionnés (maximum 3)
    selected_ids = request.GET.getlist("index_id")
    if not selected_ids and index_id:
        selected_ids = [str(index_id)]

    # Limiter à 3 index maximum
    selected_ids = selected_ids[:3] if len(selected_ids) <= 3 else selected_ids[:3]

    # Utiliser l'intersection des QuerySets pour ne garder que les favoris sélectionnés
    selected_indexes = favorites.filter(id__in=selected_ids)

    # Récupération des paramètres de dates
    start_a = request.GET.get("start_a")
    end_a = request.GET.get("end_a")
    start_b = request.GET.get("start_b")
    end_b = request.GET.get("end_b")

    # Préparation des données pour le graphique
    series_data = []
    period_stats = {}

    if selected_indexes.exists():
        for idx in selected_indexes:
            values = IndexValue.objects.filter(index=idx).order_by("date")
            if values.exists():
                dates = [v.date.strftime("%Y-%m-%d") for v in values]
                vals = [float(v.value) for v in values]
                series_data.append({
                    "name": idx.name,
                    "id": idx.id,
                    "dates": dates,
                    "values": vals,
                })

        # Calcul des statistiques si toutes les dates sont fournies
        if all([start_a, end_a, start_b, end_b]):
            try:
                date_a_start = datetime.strptime(start_a, "%Y-%m-%d").date()
                date_a_end = datetime.strptime(end_a, "%Y-%m-%d").date()
                date_b_start = datetime.strptime(start_b, "%Y-%m-%d").date()
                date_b_end = datetime.strptime(end_b, "%Y-%m-%d").date()

                # Validation des dates
                if date_a_start >= date_a_end or date_b_start >= date_b_end:
                    raise ValueError("Dates invalides")

                for idx in selected_indexes:
                    values = IndexValue.objects.filter(index=idx).order_by("date")

                    # Filtrage des valeurs pour chaque période
                    values_a = [
                        float(v.value) for v in values
                        if date_a_start <= v.date <= date_a_end
                    ]
                    values_b = [
                        float(v.value) for v in values
                        if date_b_start <= v.date <= date_b_end
                    ]

                    # Calcul des statistiques si on a des données
                    if values_a and values_b:
                        mean_a = mean(values_a)
                        mean_b = mean(values_b)
                        variation = ((mean_b - mean_a) / mean_a) * 100 if mean_a != 0 else 0

                        period_stats[idx.name] = {
                            "min_a": min(values_a),
                            "max_a": max(values_a),
                            "mean_a": round(mean_a, 2),
                            "min_b": min(values_b),
                            "max_b": max(values_b),
                            "mean_b": round(mean_b, 2),
                            "delta": round(mean_b - mean_a, 2),  # Ajout du calcul du delta
                            "variation": round(variation, 2),
                            "count_a": len(values_a),
                            "count_b": len(values_b)
                        }

            except (ValueError, TypeError) as e:
                print(f"❌ Erreur de calcul des périodes : {e}")
                # En cas d'erreur, on vide les statistiques
                period_stats = {}

    context = {
        "user_favorites": favorites,
        "selected_indexes": selected_indexes,
        "series_data": json.dumps(series_data, cls=DjangoJSONEncoder),
        "period_stats": period_stats,
        "start_a": start_a,
        "end_a": end_a,
        "start_b": start_b,
        "end_b": end_b,
        "max_indexes": 3,  # Limite d'index sélectionnables
        "user_plan": user_profile.subscription_plan,
        "index_limit": user_profile.index_limit(),
    }

    return render(request, "index_viewer.html", context)


@login_required
def toggle_favorite_ajax(request, index_id):
    """
    Vue AJAX pour basculer le statut favori d'un index
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        index = get_object_or_404(Index, id=index_id)
        user_profile = request.user.userprofile

        if index in user_profile.favorite_indexes.all():
            user_profile.favorite_indexes.remove(index)
            is_favorite = False
        else:
            # Vérifier la limite d'index
            if not user_profile.can_add_favorite():
                return JsonResponse({
                    "error": f"Limite d'index atteinte ({user_profile.index_limit()})",
                    "is_favorite": False
                }, status=400)

            user_profile.favorite_indexes.add(index)
            is_favorite = True

        return JsonResponse({
            "is_favorite": is_favorite,
            "favorites_count": user_profile.favorite_indexes.count(),
            "index_limit": user_profile.index_limit()
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def get_index_data_ajax(request, index_id):
    """
    Vue AJAX pour récupérer les données d'un index spécifique
    """
    try:
        index = get_object_or_404(Index, id=index_id)
        user_profile = request.user.userprofile

        # Vérifier que l'index est dans les favoris de l'utilisateur
        if index not in user_profile.favorite_indexes.all():
            return JsonResponse({"error": "Index non autorisé"}, status=403)

        values = IndexValue.objects.filter(index=index).order_by("date")

        data = {
            "id": index.id,
            "name": index.name,
            "unit": index.unit,
            "category": index.category,
            "dates": [v.date.strftime("%Y-%m-%d") for v in values],
            "values": [float(v.value) for v in values],
            "count": values.count(),
            "date_range": {
                "start": values.first().date.strftime("%Y-%m-%d") if values.exists() else None,
                "end": values.last().date.strftime("%Y-%m-%d") if values.exists() else None
            }
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def export_analysis_data(request):
    """
    Vue pour exporter les données d'analyse en JSON ou CSV
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        # Récupération des paramètres
        selected_ids = request.POST.getlist("index_id")
        start_a = request.POST.get("start_a")
        end_a = request.POST.get("end_a")
        start_b = request.POST.get("start_b")
        end_b = request.POST.get("end_b")
        export_format = request.POST.get("format", "json")

        user_profile = request.user.userprofile
        selected_indexes = user_profile.favorite_indexes.filter(id__in=selected_ids[:3])

        export_data = {
            "analysis_date": datetime.now().isoformat(),
            "user": request.user.username,
            "periods": {
                "period_1": {"start": start_a, "end": end_a},
                "period_2": {"start": start_b, "end": end_b}
            },
            "indexes": []
        }

        if all([start_a, end_a, start_b, end_b]):
            date_a_start = datetime.strptime(start_a, "%Y-%m-%d").date()
            date_a_end = datetime.strptime(end_a, "%Y-%m-%d").date()
            date_b_start = datetime.strptime(start_b, "%Y-%m-%d").date()
            date_b_end = datetime.strptime(end_b, "%Y-%m-%d").date()

            for idx in selected_indexes:
                values = IndexValue.objects.filter(index=idx).order_by("date")

                values_a = [v for v in values if date_a_start <= v.date <= date_a_end]
                values_b = [v for v in values if date_b_start <= v.date <= date_b_end]

                if values_a and values_b:
                    vals_a = [float(v.value) for v in values_a]
                    vals_b = [float(v.value) for v in values_b]

                    mean_a = mean(vals_a)
                    mean_b = mean(vals_b)
                    variation = ((mean_b - mean_a) / mean_a) * 100 if mean_a != 0 else 0

                    index_data = {
                        "name": idx.name,
                        "unit": idx.unit,
                        "category": idx.category,
                        "period_1": {
                            "min": min(vals_a),
                            "max": max(vals_a),
                            "mean": round(mean_a, 2),
                            "count": len(vals_a)
                        },
                        "period_2": {
                            "min": min(vals_b),
                            "max": max(vals_b),
                            "mean": round(mean_b, 2),
                            "count": len(vals_b)
                        },
                        "variation_percent": round(variation, 2)
                    }

                    export_data["indexes"].append(index_data)

        if export_format == "csv":
            # TODO: Implémenter l'export CSV si nécessaire
            pass

        return JsonResponse(export_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)