from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from main.models import Index, UserProfile
from django.contrib import messages
from django.http import JsonResponse

@login_required
def toggle_favorite(request, index_id):
    if request.method == 'POST':
        index = get_object_or_404(Index, id=index_id)
        user_profile = request.user.userprofile

        # Vérifier si l'index est déjà dans les favoris
        if index in user_profile.favorite_indexes.all():
            # SUPPRESSION - Vérifier les limites de changements AVANT de supprimer
            would_exceed_limit = (user_profile.favorite_changes_count >= user_profile.change_limit()) and user_profile.subscription_plan != 'premium'

            if would_exceed_limit:
                plan_names = {
                    'free': 'Free',
                    '5_index': '5 Index', 
                    '10_index': '10 Index',
                    'premium': 'Premium'
                }
                plan_display = plan_names.get(user_profile.subscription_plan, user_profile.subscription_plan)

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': True,
                        'type': 'no_changes_left',
                        'title': 'No changes remaining',
                        'message': f'You have used all {user_profile.change_limit()} allowed changes for your {plan_display} plan.',
                        'upgrade_message': 'Upgrade your plan to get more changes or unlimited access.',
                        'current_plan': plan_display,
                        'max_indexes': user_profile.index_limit(),
                        'current_count': user_profile.favorite_indexes.count()
                    })

            # Suppression autorisée
            user_profile.favorite_indexes.remove(index)
            user_profile.favorite_changes_count += 1
            user_profile.save()

            is_favorite = False
            message = 'Index removed from favorites'
        else:
            # AJOUT - vérifier les limites selon le plan
            current_favorites_count = user_profile.favorite_indexes.count()
            max_indexes = user_profile.index_limit()

            if current_favorites_count >= max_indexes:
                # Limite d'index atteinte
                plan_names = {
                    'free': 'Free',
                    '5_index': '5 Index', 
                    '10_index': '10 Index',
                    'premium': 'Premium'
                }
                plan_display = plan_names.get(user_profile.subscription_plan, user_profile.subscription_plan)
                error_message = f'Limit reached! Your {plan_display} plan allows {max_indexes} indexes maximum.'
                upgrade_message = 'Upgrade to a higher plan to add more indexes to your favorites.'

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': True,
                        'type': 'limit_reached',
                        'title': 'Index limit reached',
                        'message': error_message,
                        'upgrade_message': upgrade_message,
                        'current_plan': plan_display,
                        'max_indexes': max_indexes,
                        'current_count': current_favorites_count
                    })
                messages.error(request, f'{error_message} {upgrade_message}')
                return redirect('main:liste_index')

            # Vérifier les limites de changements AVANT d'ajouter
            would_exceed_limit = (user_profile.favorite_changes_count >= user_profile.change_limit()) and user_profile.subscription_plan != 'premium'
            is_very_first_action = (user_profile.favorite_changes_count == 0 and current_favorites_count == 0)

            if not is_very_first_action and would_exceed_limit:
                plan_names = {
                    'free': 'Free',
                    '5_index': '5 Index', 
                    '10_index': '10 Index',
                    'premium': 'Premium'
                }
                plan_display = plan_names.get(user_profile.subscription_plan, user_profile.subscription_plan)

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': True,
                        'type': 'no_changes_left',
                        'title': 'No changes remaining',
                        'message': f'You have used all {user_profile.change_limit()} allowed changes for your {plan_display} plan.',
                        'upgrade_message': 'Upgrade your plan to get more changes or unlimited access.',
                        'current_plan': plan_display,
                        'max_indexes': max_indexes,
                        'current_count': current_favorites_count
                    })

            # Ajout autorisé
            user_profile.favorite_indexes.add(index)

            # Seul le tout premier ajout est gratuit            
            if not is_very_first_action:
                user_profile.favorite_changes_count += 1
                user_profile.save()

            is_favorite = True
            message = 'Index added to favorites'

        # Si c'est une requête AJAX, retourner JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'is_favorite': is_favorite,
                'message': message
            })

        # Sinon, redirection classique (pour compatibilité)
        messages.success(request, message)
        return redirect('main:liste_index')

    return redirect('main:liste_index')

@login_required 
def get_user_plan_status(request):
    """API pour obtenir le statut du plan utilisateur"""
    user_profile = request.user.userprofile

    current_count = user_profile.favorite_indexes.count()
    max_indexes = user_profile.index_limit()
    max_changes = user_profile.change_limit()
    remaining_changes = max_changes - user_profile.favorite_changes_count

    return JsonResponse({
        'plan': user_profile.subscription_plan,
        'current_indexes': current_count,
        'max_indexes': max_indexes if max_indexes != float('inf') else 'unlimited',
        'current_changes': user_profile.favorite_changes_count,
        'max_changes': max_changes if max_changes != float('inf') else 'unlimited',
        'remaining_changes': remaining_changes if remaining_changes != float('inf') else 'unlimited',
        'can_add_index': current_count < max_indexes,
        'can_change_index': remaining_changes > 0 or user_profile.subscription_plan == 'premium'
    })