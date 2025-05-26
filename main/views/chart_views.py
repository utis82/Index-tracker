from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from main.models import Index, IndexValue
from main.decorators import subscription_required
from django.core.serializers.json import DjangoJSONEncoder
from statistics import mean
from datetime import datetime
import json


@login_required
@subscription_required
def index_viewer(request, index_id=None):
    all_indexes = Index.objects.all().order_by("name")
    user_profile = request.user.userprofile
    favorites = user_profile.favorite_indexes.all()

    selected_ids = request.GET.getlist("index_id")
    if not selected_ids:
        if index_id:
            selected_ids = [str(index_id)]
        elif favorites.exists():
            selected_ids = [str(favorites.first().id)]

    selected_indexes = Index.objects.filter(id__in=selected_ids)
    current_index = selected_indexes.first() if selected_indexes else None

    series_data = []
    for idx in selected_indexes:
        values = IndexValue.objects.filter(index=idx).order_by("date")
        if values.exists():
            dates = [v.date.strftime("%Y-%m-%d") for v in values]
            vals = [v.value for v in values]
            series_data.append({
                "name": idx.name,
                "id": idx.id,
                "dates": dates,
                "values": vals,
            })

    start_a = request.GET.get("start_a")
    end_a = request.GET.get("end_a")
    start_b = request.GET.get("start_b")
    end_b = request.GET.get("end_b")

    period_stats = {}

    if start_a and end_a and start_b and end_b:
        try:
            date_a_start = datetime.strptime(start_a, "%Y-%m-%d").date()
            date_a_end = datetime.strptime(end_a, "%Y-%m-%d").date()
            date_b_start = datetime.strptime(start_b, "%Y-%m-%d").date()
            date_b_end = datetime.strptime(end_b, "%Y-%m-%d").date()

            for idx in selected_indexes:
                values = IndexValue.objects.filter(index=idx).order_by("date")
                values_a = [
                    v.value for v in values
                    if date_a_start <= v.date <= date_a_end
                ]
                values_b = [
                    v.value for v in values
                    if date_b_start <= v.date <= date_b_end
                ]

                if values_a and values_b:
                    mean_a = mean(values_a)
                    mean_b = mean(values_b)
                    variation = ((mean_b - mean_a) / mean_a) * 100

                    period_stats[idx.name] = {
                        "min_a": min(values_a),
                        "max_a": max(values_a),
                        "mean_a": round(mean_a, 2),
                        "min_b": min(values_b),
                        "max_b": max(values_b),
                        "mean_b": round(mean_b, 2),
                        "variation": round(variation, 2)
                    }

        except Exception as e:
            print("❌ Erreur de calcul des périodes :", e)

    return render(
        request, "index_viewer.html", {
            "all_indexes": all_indexes,
            "user_favorites": favorites,
            "selected_indexes": selected_indexes,
            "current_index": current_index,
            "series_data": json.dumps(series_data, cls=DjangoJSONEncoder),
            "period_stats": period_stats,
            "start_a": start_a,
            "end_a": end_a,
            "start_b": start_b,
            "end_b": end_b,
        })

