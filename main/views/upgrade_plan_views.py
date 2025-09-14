# main/views/upgrade_plan_views.py

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import render
import json

@login_required
def upgrade_plan_view(request):
    """Vue pour afficher la page d'upgrade des plans"""
    context = {
        # Le contexte user est automatiquement disponible dans les templates
        # Vous pouvez ajouter d'autres données si nécessaire
    }
    return render(request, "upgrade_plan.html", context)

@require_POST
@login_required
def upgrade_plan_api(request):
    """API pour gérer les upgrades de plan"""
    try:
        data = json.loads(request.body)
        new_plan = data.get('new_plan')

        # Validation du plan
        valid_plans = ['free', '5_index', '10_index', 'premium']
        if new_plan not in valid_plans:
            return JsonResponse({
                'success': False,
                'message': 'Invalid plan selected'
            })
        
        # Block downgrades to free - must use secure cancellation endpoint
        if new_plan == 'free':
            return JsonResponse({
                'success': False,
                'message': 'Please use the cancellation option to downgrade to free plan'
            })
        
        # Block upgrades to any paid plan - must go through Stripe checkout
        paid_plans = ['5_index', '10_index', 'premium']
        if new_plan in paid_plans:
            return JsonResponse({
                'success': False,
                'message': 'Please use the upgrade buttons to purchase a paid plan'
            })

        user_profile = request.user.userprofile
        old_plan = user_profile.subscription_plan

        # Vérification si c'est un vrai changement
        if old_plan == new_plan:
            return JsonResponse({
                'success': False,
                'message': 'You are already on this plan'
            })

        # Vérification des limites pour un downgrade
        if new_plan != 'premium':
            # Obtenir la nouvelle limite
            plan_limits = {
                'free': 1,
                '5_index': 5,
                '10_index': 10,
            }
            new_limit = plan_limits.get(new_plan, 1)
            current_favorites = user_profile.favorite_indexes.count()

            if current_favorites > new_limit:
                return JsonResponse({
                    'success': False,
                    'message': f'You have {current_favorites} indexes but the {new_plan} plan only allows {new_limit}. Please remove some indexes first.'
                })

        # Effectuer le changement
        user_profile.subscription_plan = new_plan
        user_profile.save()

        # Log du changement (optionnel)
        print(f"User {request.user.username} changed plan from {old_plan} to {new_plan}")

        return JsonResponse({
            'success': True,
            'message': f'Successfully changed to {new_plan} plan',
            'old_plan': old_plan,
            'new_plan': new_plan
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request format'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error upgrading plan: {str(e)}'
        })