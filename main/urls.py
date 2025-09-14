# main/urls.py
from django.urls import path
from main.views.base_views import (
    home,
    login_view,
    dashboard,
    register_view,
    upload_excel,
    logout_view,
    search_index,
    choose_primary_index,
    contact_view,
    verify_email,
    resend_verification_code,
    cleanup_duplicate_indexes,
    CustomPasswordChangeView,
    CustomPasswordChangeDoneView,
    # SUPPRIMÉ: upgrade_plan_view, upgrade_plan_api (maintenant dans upgrade_plan_views)
    password_reset_request,
    password_reset_code,
    password_reset_confirm,
    resend_password_reset_code)
from main.views.index_views import liste_index_view
from main.views.chart_views import (index_viewer, toggle_favorite_ajax,
                                    get_index_data_ajax, export_analysis_data,
                                    export_analysis_excel)
from main.views.user_views import toggle_favorite, get_user_plan_status
from main.views.prix_indexes_views import prix_indexes_view, delete_structure, get_structure_data
from main.views import prix_indexes_views
# NOUVEAU: Import depuis upgrade_plan_views
from main.views.upgrade_plan_views import upgrade_plan_view, upgrade_plan_api
# Import payment views for Stripe integration
from main.views.payment_views import create_checkout_session, payment_success, stripe_webhook, cancel_subscription

app_name = 'main'
urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('verify-email/<int:user_id>/', verify_email, name='verify_email'),
    path('resend-code/<int:user_id>/',
         resend_verification_code,
         name='resend_verification_code'),
    path('dashboard/', dashboard, name='dashboard'),
    path('change-password/',
         CustomPasswordChangeView.as_view(),
         name='password_change'),
    path('change-password/done/',
         CustomPasswordChangeDoneView.as_view(),
         name='password_change_done'),
    path('upload/', upload_excel, name='upload'),
    path('index/import-excel/', upload_excel, name='index_import_excel'),
    path('liste-index/', liste_index_view, name='liste_index'),
    path('logout/', logout_view, name='logout'),
    path('search-index/', search_index, name='search_index'),
    path('index-viewer/<int:index_id>/', index_viewer, name='index_viewer'),
    path('index-viewer/', index_viewer, name='index_viewer_home'),
    path('toggle-favorite/<int:index_id>/',
         toggle_favorite,
         name='toggle_favorite'),
    path('prix-indexes/', prix_indexes_view, name='prix_indexes'),
    path('delete-structure/<int:pk>/',
         delete_structure,
         name='delete_structure'),
    path('structure-data/<int:pk>/',
         get_structure_data,
         name='get_structure_data'),
    path("prix-indexes/delete/<int:pk>/",
         delete_structure,
         name="delete_structure"),
    path('get-part-data/<int:part_id>/',
         prix_indexes_views.get_part_data,
         name='get_part_data'),
    path('index-analysis/', index_viewer, name='index_analysis'),
    path('index-analysis/<int:index_id>/',
         index_viewer,
         name='index_analysis_with_id'),
    path('toggle_favorite/<int:index_id>/',
         toggle_favorite_ajax,
         name='toggle_favorite_ajax'),
    path('api/index/<int:index_id>/data/',
         get_index_data_ajax,
         name='get_index_data'),
    path('api/analysis/export/', export_analysis_data, name='export_analysis'),
    path('contact/', contact_view, name='contact'),

    # CORRIGÉ: Maintenant depuis upgrade_plan_views
    path('upgrade-plan/', upgrade_plan_view, name='upgrade_plan'),
    path('api/upgrade-plan/', upgrade_plan_api, name='upgrade_plan_api'),
    path('api/plan-status/', get_user_plan_status, name='plan_status'),
    path('tools/cleanup-duplicates/',
         cleanup_duplicate_indexes,
         name='cleanup_duplicates'),
    path('export-analysis-excel/',
         export_analysis_excel,
         name='export_analysis_excel'),

    # Password reset URLs (restent dans base_views)
    path('password-reset/',
         password_reset_request,
         name='password_reset_request'),
    path('password-reset-code/<int:request_id>/',
         password_reset_code,
         name='password_reset_code'),
    path('password-reset-confirm/<int:request_id>/',
         password_reset_confirm,
         name='password_reset_confirm'),
    path('resend-reset-code/<int:request_id>/',
         resend_password_reset_code,
         name='resend_password_reset_code'),

    # 💳 STRIPE PAYMENT URLS
    path('payment/create-checkout-session/',
         create_checkout_session,
         name='create_checkout_session'),
    path('payment/success/', payment_success, name='payment_success'),
    path('payment/webhook/', stripe_webhook, name='stripe_webhook'),
    path('payment/cancel-subscription/',
         cancel_subscription,
         name='cancel_subscription'),
]
