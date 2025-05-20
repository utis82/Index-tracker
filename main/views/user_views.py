from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from main.models import Index, UserProfile

@login_required
def toggle_favorite(request, index_id):
    index = get_object_or_404(Index, id=index_id)
    profile = request.user.userprofile

    if index in profile.favorite_indexes.all():
        profile.favorite_indexes.remove(index)
    else:
        profile.favorite_indexes.add(index)

    return redirect(request.META.get('HTTP_REFERER', 'main:dashboard'))
