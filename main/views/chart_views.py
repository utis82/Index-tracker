from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from main.models import Index, IndexValue
from main.decorators import subscription_required
from django.core.serializers.json import DjangoJSONEncoder
import json


@login_required
@subscription_required
def index_viewer(request, index_id):
    all_indexes = Index.objects.all().order_by("name")
    user_profile = request.user.userprofile
    user_favorites = user_profile.favorite_indexes.all()
    index = get_object_or_404(Index, id=index_id)

    # 🔒 Restriction d'accès selon abonnement
    if user_profile.subscription_plan == 'free':
        if user_profile.primary_index is None:
            user_profile.primary_index = index
            user_profile.primary_index_change_count = 0
            user_profile.favorite_indexes.set([index])
            user_profile.save()
        elif index != user_profile.primary_index:
            if user_profile.primary_index_change_count < 2:
                user_profile.primary_index = index
                user_profile.primary_index_change_count += 1
                user_profile.favorite_indexes.set([index])
                user_profile.save()
            else:
                return HttpResponse(
                    "⛔ Vous avez atteint la limite de changements d’index dans le plan gratuit.",
                    status=403)
    elif user_profile.subscription_plan != 'premium' and index not in user_favorites:
        return HttpResponse(
            "⛔ Accès refusé : cet index n'est pas dans vos favoris.",
            status=403)

    values = IndexValue.objects.filter(index=index).order_by("date")
    if values.exists():
        dates = [v.date.strftime("%Y-%m-%d") for v in values]
        numbers = [v.value for v in values]
        dates_json = json.dumps(dates, cls=DjangoJSONEncoder)
        values_json = json.dumps(numbers, cls=DjangoJSONEncoder)
    else:
        dates_json = []
        values_json = []

    return render(
        request, "index_viewer.html", {
            "all_indexes": all_indexes,
            "selected_index_id": index_id,
            "current_index": index,
            "user_favorites": user_favorites,
            "dates_json": dates_json,
            "values_json": values_json,
        })
