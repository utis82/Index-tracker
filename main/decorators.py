# decorators.py

from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied

def subscription_required(view_func):
    def wrapper(request, *args, **kwargs):
        profile = request.user.userprofile
        index_id = kwargs.get('index_id')
        if profile.subscription_plan == 'premium':
            return view_func(request, *args, **kwargs)

        if index_id:
            if not profile.favorite_indexes.filter(id=index_id).exists():
                if profile.favorite_indexes.count() >= profile.index_limit():
                    raise PermissionDenied("Vous avez atteint la limite de votre forfait.")
        return view_func(request, *args, **kwargs)
    return wrapper
