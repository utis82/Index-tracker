from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from main.models import Product, Part, Slice, Index, IndexValue, UserProfile

# --- Inlines ---
class PartInline(admin.TabularInline):
    model = Part
    extra = 0
    fields = ("name",)

class SliceInline(admin.TabularInline):
    model = Slice
    extra = 0
    fields = ("label",)

class IndexValueInline(admin.TabularInline):
    model = IndexValue
    extra = 0
    fields = ("index", "value")

# --- Admin Product ---
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    inlines = [PartInline]

# --- Admin Part ---
@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("name", "product")
    search_fields = ("name", "product__name")
    list_select_related = ("product",)
    inlines = [SliceInline, IndexValueInline]

# --- Admin Slice ---
@admin.register(Slice)
class SliceAdmin(admin.ModelAdmin):
    list_display = ("label", "part")
    search_fields = ("label", "part__name")
    list_select_related = ("part",)

# --- Admin Index avec bouton Import (NETTOYÉ) ---
@admin.register(Index)
class IndexAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "category")  # Ajout unit et category pour voir
    search_fields = ("name", "category")
    list_filter = ("category",)  # Filtre par catégorie
    change_list_template = "admin/index_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'import-excel/',
                self.admin_site.admin_view(self.redirect_to_import),
                name='index_import_excel_admin'
            )
        ]
        return custom_urls + urls

    def redirect_to_import(self, request):
        """Redirige vers notre fonction d'import optimisée dans base_views.py"""
        return redirect('main:index_import_excel')

# --- Admin UserProfile ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "subscription_plan", "get_last_payment_date", "get_subscription_expiry", "get_subscription_status")
    search_fields = ("user__username", "user__email")
    list_filter = ("subscription_plan",)
    readonly_fields = ("get_subscription_info_display", "get_payment_history")
    
    def get_last_payment_date(self, obj):
        """Get user's last payment date"""
        try:
            last_payment = obj.user.stripe_payments.filter(status='succeeded').order_by('-created_at').first()
            if last_payment:
                return last_payment.created_at.strftime("%Y-%m-%d %H:%M")
            return "No payments"
        except:
            return "N/A"
    get_last_payment_date.short_description = "Last Payment"
    get_last_payment_date.admin_order_field = "user__stripe_payments__created_at"
    
    def get_subscription_expiry(self, obj):
        """Get user's subscription expiry date"""
        try:
            subscription = obj.user.stripe_subscriptions.filter(
                status__in=['active', 'trialing', 'past_due']
            ).order_by('-created_at').first()
            if subscription:
                return subscription.current_period_end.strftime("%Y-%m-%d")
            return "No active subscription"
        except:
            return "N/A"
    get_subscription_expiry.short_description = "Expires"
    get_subscription_expiry.admin_order_field = "user__stripe_subscriptions__current_period_end"
    
    def get_subscription_status(self, obj):
        """Get user's subscription status with color coding"""
        try:
            from django.utils.html import format_html
            subscription = obj.user.stripe_subscriptions.filter(
                status__in=['active', 'trialing', 'past_due']
            ).order_by('-created_at').first()
            if subscription:
                status = subscription.status
                if status == 'active':
                    return format_html('<span style="color: green; font-weight: bold;">✓ {}</span>', status.title())
                elif status == 'past_due':
                    return format_html('<span style="color: orange; font-weight: bold;">⚠ {}</span>', status.title())
                else:
                    return format_html('<span style="color: blue;">{}</span>', status.title())
            return format_html('<span style="color: gray;">No subscription</span>')
        except:
            return "N/A"
    get_subscription_status.short_description = "Status"
    
    def get_subscription_info_display(self, obj):
        """Detailed subscription information for admin detail view"""
        try:
            from django.utils.html import format_html
            html = []
            
            # Current subscription
            subscription = obj.user.stripe_subscriptions.filter(
                status__in=['active', 'trialing', 'past_due']
            ).order_by('-created_at').first()
            
            if subscription:
                html.append(f"<h3>Active Subscription</h3>")
                html.append(f"<p><strong>Plan:</strong> {subscription.subscription_plan}</p>")
                html.append(f"<p><strong>Status:</strong> {subscription.status}</p>")
                html.append(f"<p><strong>Started:</strong> {subscription.current_period_start.strftime('%Y-%m-%d %H:%M')}</p>")
                html.append(f"<p><strong>Expires:</strong> {subscription.current_period_end.strftime('%Y-%m-%d %H:%M')}</p>")
                html.append(f"<p><strong>Stripe ID:</strong> {subscription.stripe_subscription_id}</p>")
            else:
                html.append(f"<h3>No Active Subscription</h3>")
            
            return format_html(''.join(html))
        except Exception as e:
            return f"Error loading subscription info: {str(e)}"
    get_subscription_info_display.short_description = "Subscription Details"
    
    def get_payment_history(self, obj):
        """Payment history for admin detail view"""
        try:
            from django.utils.html import format_html
            payments = obj.user.stripe_payments.order_by('-created_at')[:5]  # Last 5 payments
            
            if not payments:
                return format_html("<p>No payment history</p>")
            
            html = ["<h3>Recent Payments (Last 5)</h3>", "<table border='1' style='width:100%; border-collapse: collapse;'>"]
            html.append("<tr style='background-color: #f0f0f0;'><th>Date</th><th>Amount</th><th>Status</th><th>Plan</th></tr>")
            
            for payment in payments:
                status_color = 'green' if payment.status == 'succeeded' else 'red'
                html.append(f"""
                <tr>
                    <td>{payment.created_at.strftime('%Y-%m-%d %H:%M')}</td>
                    <td>{payment.amount} {payment.currency}</td>
                    <td style='color: {status_color}; font-weight: bold;'>{payment.status}</td>
                    <td>{payment.subscription_plan}</td>
                </tr>
                """)
            
            html.append("</table>")
            return format_html(''.join(html))
        except Exception as e:
            return f"Error loading payment history: {str(e)}"
    get_payment_history.short_description = "Payment History"