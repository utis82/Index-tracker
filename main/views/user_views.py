from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from main.models import Index, UserProfile
from django.contrib import messages

@login_required
def toggle_favorite(request, index_id):
    user_profile = request.user.userprofile
    index = get_object_or_404(Index, id=index_id)

    if index in user_profile.favorite_indexes.all():
        user_profile.favorite_indexes.remove(index)
    else:
        if not user_profile.can_add_favorite():
            messages.error(request, "Vous avez atteint la limite d’index favoris pour votre plan.")
        else:
            user_profile.favorite_indexes.add(index)

    return redirect('main:index_viewer', index_id=index_id)

@login_required
def choose_primary_index(request):
    if request.method == 'POST':
        index_id = request.POST.get('index_id')
        selected_index = get_object_or_404(Index, id=index_id)
        user_profile = request.user.userprofile

        # Vérifie s’il essaie de changer pour un index différent
        if user_profile.primary_index != selected_index:
            if not user_profile.can_modify_favorites():
                messages.error(
                    request,
                    f"Limite atteinte : vous ne pouvez changer votre index principal que {user_profile.change_limit()} fois."
                )
                return redirect('main:dashboard')

            user_profile.primary_index = selected_index
            user_profile.primary_index_change_count += 1
            user_profile.save()
            messages.success(request, "Index principal mis à jour.")
        else:
            messages.info(request, "Cet index est déjà votre favori principal.")

        return redirect('main:dashboard')
