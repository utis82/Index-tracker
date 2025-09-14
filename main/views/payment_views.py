# main/views/payment_views.py

import json
import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.utils.decorators import method_decorator
from django.views import View
import logging

from main.models import StripeCustomer, StripeSubscription, StripePayment, UserProfile

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)


@login_required
@require_POST
def cancel_subscription(request):
    """Cancel user's Stripe subscription and downgrade to free plan"""
    try:
        user = request.user
        
        # ALWAYS check Stripe for ALL subscriptions - don't rely only on local records
        # This ensures we find and cancel any subscriptions that might not be in our local DB
        active_statuses = ['active', 'trialing', 'past_due', 'unpaid', 'incomplete']
        
        try:
            stripe_customer = StripeCustomer.objects.get(user=user)
        except StripeCustomer.DoesNotExist:
            # No Stripe customer record found - check if user truly has no subscriptions
            user_profile = user.userprofile
            if user_profile.subscription_plan == 'free':
                return JsonResponse({
                    'success': True,
                    'message': 'Already on free plan'
                })
            else:
                # User has a paid plan locally but no Stripe customer - suspicious
                logger.warning(f"User {user.username} has paid plan '{user_profile.subscription_plan}' but no StripeCustomer record")
                return JsonResponse({
                    'success': False,
                    'error': 'Unable to verify subscription status. Please contact support.'
                })
        
        # Get ALL subscriptions from Stripe with full pagination
        all_subscriptions = []
        starting_after = None
        
        try:
            while True:
                # List subscriptions with pagination
                list_params = {
                    'customer': stripe_customer.stripe_customer_id,
                    'status': 'all',
                    'limit': 100  # Max allowed by Stripe
                }
                if starting_after:
                    list_params['starting_after'] = starting_after
                
                subscription_page = stripe.Subscription.list(**list_params)
                
                all_subscriptions.extend(subscription_page.data)
                
                # Check if there are more pages
                if not subscription_page.has_more:
                    break
                    
                # Get the last subscription ID for pagination
                starting_after = subscription_page.data[-1]['id']
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error listing subscriptions for user {user.username}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Unable to verify subscription status due to payment service error. Please try again later or contact support.'
            })
        
        # Find and cancel ALL active subscriptions
        cancelled_count = 0
        failed_cancellations = []
        
        for subscription in all_subscriptions:
            if subscription['status'] in active_statuses:
                try:
                    # Cancel this subscription
                    stripe.Subscription.modify(
                        subscription['id'],
                        cancel_at_period_end=True
                    )
                    
                    # Create or update local record
                    StripeSubscription.objects.update_or_create(
                        stripe_subscription_id=subscription['id'],
                        defaults={
                            'user': user,
                            'stripe_customer': stripe_customer,
                            'subscription_plan': get_plan_from_subscription(subscription),
                            'status': subscription['status'],
                            'current_period_start': subscription['current_period_start'],
                            'current_period_end': subscription['current_period_end'],
                        }
                    )
                    
                    cancelled_count += 1
                    logger.info(f"Cancelled Stripe subscription {subscription['id']} for user {user.username}")
                    
                except stripe.error.StripeError as e:
                    logger.error(f"Failed to cancel Stripe subscription {subscription['id']}: {str(e)}")
                    failed_cancellations.append(subscription['id'])
        
        # If any cancellations failed, return error - cannot proceed to free plan
        if failed_cancellations:
            return JsonResponse({
                'success': False,
                'error': f'Unable to cancel all subscriptions (failed: {len(failed_cancellations)}). Please contact support.'
            })
        
        if cancelled_count > 0:
            # Don't change plan to free here - let webhook handle it after Stripe confirms
            return JsonResponse({
                'success': True,
                'message': f'Cancelled {cancelled_count} subscription(s) successfully. Access will continue until the end of your billing period.'
            })
        
        # No active subscriptions found - user is already effectively on free
        # Don't change plan here - just inform user
        return JsonResponse({
            'success': True,
            'message': 'No active subscriptions found. You are already on the free plan or will be after your current billing period ends.'
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error cancelling subscription: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error cancelling subscription. Please contact support.'
        })
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please contact support.'
        })

@login_required
@require_POST 
def create_checkout_session(request):
    """Create a Stripe checkout session for plan upgrade"""
    try:
        data = json.loads(request.body)
        plan_type = data.get('plan_type')
        
        # Validate plan type
        if plan_type not in ['5_index', '10_index', 'premium']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid plan type'
            })
            
        # Get or create Stripe customer
        stripe_customer, created = StripeCustomer.objects.get_or_create(
            user=request.user,
            defaults={
                'stripe_customer_id': ''
            }
        )
        
        # Create Stripe customer if needed
        if created or not stripe_customer.stripe_customer_id:
            customer = stripe.Customer.create(
                email=request.user.email,
                name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                metadata={
                    'user_id': request.user.id,
                    'username': request.user.username
                }
            )
            stripe_customer.stripe_customer_id = customer.id
            stripe_customer.save()
        
        # Get price ID for the plan
        price_id = settings.STRIPE_PRICE_IDS.get(plan_type)
        if not price_id:
            return JsonResponse({
                'success': False,
                'error': f'Price ID not configured for plan: {plan_type}'
            })
        
        # Get current domain for success/cancel URLs
        domain = request.build_absolute_uri('/')[:-1]  # Remove trailing slash
        
        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=stripe_customer.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f'{domain}/payment/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{domain}/upgrade-plan',
            metadata={
                'user_id': request.user.id,
                'plan_type': plan_type,
            }
        )
        
        return JsonResponse({
            'success': True,
            'checkout_url': session.url,
            'session_id': session.id
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Payment processing error. Please try again.'
        })
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        })


@login_required
def payment_success(request):
    """Handle successful payment and update user plan"""
    session_id = request.GET.get('session_id')
    
    if not session_id:
        return JsonResponse({
            'success': False,
            'error': 'No session ID provided'
        })
    
    try:
        # Retrieve the checkout session with expanded data
        session = stripe.checkout.Session.retrieve(
            session_id, 
            expand=['subscription', 'customer']
        )
        
        # Verify this session belongs to the authenticated user
        user_id_from_session = session.metadata.get('user_id')
        if not user_id_from_session or int(user_id_from_session) != request.user.id:
            logger.error(f"Session user_id mismatch: session={user_id_from_session}, user={request.user.id}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid session for this user'
            })
        
        if session.payment_status == 'paid':
            # Get the plan type from metadata
            plan_type = session.metadata.get('plan_type')
            if not plan_type:
                logger.error(f"No plan_type in session metadata: {session_id}")
                return JsonResponse({
                    'success': False,
                    'error': 'Plan type not found in session'
                })
            
            # Update or create Stripe customer record
            stripe_customer, created = StripeCustomer.objects.update_or_create(
                user=request.user,
                defaults={
                    'stripe_customer_id': session.customer.id if hasattr(session.customer, 'id') else session.customer,
                }
            )
            
            # If there's a subscription, create/update subscription record safely
            if session.subscription:
                subscription_data = session.subscription
                if isinstance(subscription_data, str):
                    # If it's just an ID, retrieve the full subscription
                    subscription_data = stripe.Subscription.retrieve(subscription_data)
                
                from datetime import datetime, timezone, timedelta
                
                # Safely extract timestamps (may not be available immediately after checkout)
                current_period_start = None
                current_period_end = None
                
                if hasattr(subscription_data, 'current_period_start') and subscription_data.current_period_start:
                    current_period_start = datetime.fromtimestamp(subscription_data.current_period_start, tz=timezone.utc)
                elif hasattr(subscription_data, 'get'):
                    start_timestamp = subscription_data.get('current_period_start')
                    if start_timestamp:
                        current_period_start = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
                
                if hasattr(subscription_data, 'current_period_end') and subscription_data.current_period_end:
                    current_period_end = datetime.fromtimestamp(subscription_data.current_period_end, tz=timezone.utc)
                elif hasattr(subscription_data, 'get'):
                    end_timestamp = subscription_data.get('current_period_end')
                    if end_timestamp:
                        current_period_end = datetime.fromtimestamp(end_timestamp, tz=timezone.utc)
                
                # If timestamps are missing, use fallback values
                if not current_period_start:
                    current_period_start = datetime.now(tz=timezone.utc)
                    logger.warning(f"Missing current_period_start for subscription {subscription_data.id}, using current time")
                
                if not current_period_end:
                    current_period_end = current_period_start + timedelta(days=30)
                    logger.warning(f"Missing current_period_end for subscription {subscription_data.id}, using 30-day default")
                
                stripe_subscription, sub_created = StripeSubscription.objects.update_or_create(
                    stripe_subscription_id=subscription_data.id,
                    defaults={
                        'user': request.user,
                        'stripe_customer': stripe_customer,
                        'subscription_plan': plan_type,
                        'status': subscription_data.status,
                        'current_period_start': current_period_start,
                        'current_period_end': current_period_end,
                    }
                )
            else:
                # For one-time payments (no subscription), create a basic subscription record
                from datetime import datetime, timezone, timedelta
                now = datetime.now(tz=timezone.utc)
                # Set a 30-day period for one-time payments as a default
                period_end = now + timedelta(days=30)
                
                stripe_subscription, sub_created = StripeSubscription.objects.update_or_create(
                    stripe_subscription_id=f"onetime_{session.id}",  # Use session ID as unique identifier
                    defaults={
                        'user': request.user,
                        'stripe_customer': stripe_customer,
                        'subscription_plan': plan_type,
                        'status': 'active',  # One-time payment is considered active
                        'current_period_start': now,
                        'current_period_end': period_end,
                    }
                )
            
            # Create payment record (only if payment_intent exists)
            if session.payment_intent:
                StripePayment.objects.create(
                    user=request.user,
                    stripe_payment_intent_id=session.payment_intent,
                    stripe_customer=stripe_customer,
                    amount=session.amount_total / 100,  # Convert from cents
                    currency=session.currency.upper(),
                    status='succeeded',
                    subscription_plan=plan_type
                )
            else:
                logger.info(f"No payment_intent in session {session.id}, skipping payment record creation")
            
            # CRITICAL: Update user's subscription plan
            user_profile = request.user.userprofile
            user_profile.subscription_plan = plan_type
            user_profile.save()
            
            logger.info(f"Successfully updated user {request.user.username} to plan {plan_type}")
            
            # Check if request wants JSON response (for AJAX calls)
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': f'Payment successful! Your {plan_type} plan is now active.',
                    'plan_type': plan_type,
                    'redirect_url': '/dashboard/'
                })
            
            # For regular browser requests, redirect to dashboard with success message
            from django.contrib import messages
            from django.shortcuts import redirect
            
            messages.success(request, f'🎉 Payment successful! Your {plan_type.replace("_", " ").title()} plan is now active.')
            return redirect('/dashboard/')
            
        else:
            return JsonResponse({
                'success': False,
                'error': 'Payment was not completed successfully'
            })
            
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving session: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error verifying payment. Please contact support.'
        })
    except Exception as e:
        logger.error(f"Error processing payment success: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please contact support.'
        })


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        return HttpResponse(status=400)
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        handle_checkout_session_completed(event['data']['object'])
    elif event['type'] == 'customer.subscription.created':
        handle_subscription_created(event['data']['object'])
    elif event['type'] == 'customer.subscription.updated':
        handle_subscription_updated(event['data']['object'])
    elif event['type'] == 'customer.subscription.deleted':
        handle_subscription_deleted(event['data']['object'])
    elif event['type'] == 'invoice.payment_succeeded':
        handle_payment_succeeded(event['data']['object'])
    elif event['type'] == 'invoice.payment_failed':
        handle_payment_failed(event['data']['object'])
    else:
        logger.info(f"Unhandled Stripe webhook event type: {event['type']}")
    
    return HttpResponse(status=200)


def handle_checkout_session_completed(session):
    """Handle completed checkout session - DO NOT activate plan yet"""
    try:
        user_id = session['metadata'].get('user_id')
        plan_type = session['metadata'].get('plan_type')
        
        if not user_id or not plan_type:
            logger.error("Missing user_id or plan_type in checkout session metadata")
            return
        
        user = User.objects.get(id=user_id)
        
        # DO NOT update user's subscription plan here!
        # Wait for subscription.created/updated with status='active'
        # This prevents granting access before payment is fully confirmed
        
        logger.info(f"Checkout session completed for user {user.username}, plan {plan_type}. Waiting for subscription activation.")
        
    except User.DoesNotExist:
        logger.error(f"User not found for checkout session: {session['id']}")
    except Exception as e:
        logger.error(f"Error handling checkout session completed: {str(e)}")


def handle_subscription_created(subscription):
    """Handle new subscription creation"""
    try:
        # Get the customer and user
        stripe_customer = StripeCustomer.objects.get(
            stripe_customer_id=subscription['customer']
        )
        
        # Determine plan type from subscription items
        plan_type = get_plan_from_subscription(subscription)
        
        # Create or update StripeSubscription record
        stripe_subscription, created = StripeSubscription.objects.update_or_create(
            stripe_subscription_id=subscription['id'],
            defaults={
                'user': stripe_customer.user,
                'stripe_customer': stripe_customer,
                'subscription_plan': plan_type,
                'status': subscription['status'],
                'current_period_start': subscription['current_period_start'],
                'current_period_end': subscription['current_period_end'],
            }
        )
        
        # ONLY activate user's plan if subscription is active
        # Do not grant access for incomplete, trialing, or other non-active states
        if subscription['status'] == 'active':
            user_profile = stripe_customer.user.userprofile
            user_profile.subscription_plan = plan_type
            user_profile.save()
            logger.info(f"Activated {plan_type} plan for user {stripe_customer.user.username}")
        else:
            logger.info(f"Created subscription for user {stripe_customer.user.username} with status {subscription['status']} - waiting for activation")
        
    except StripeCustomer.DoesNotExist:
        logger.error(f"StripeCustomer not found for subscription: {subscription['id']}")
    except Exception as e:
        logger.error(f"Error handling subscription created: {str(e)}")


def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    try:
        stripe_subscription = StripeSubscription.objects.get(
            stripe_subscription_id=subscription['id']
        )
        
        # Update subscription details
        stripe_subscription.status = subscription['status']
        stripe_subscription.current_period_start = subscription['current_period_start']
        stripe_subscription.current_period_end = subscription['current_period_end']
        stripe_subscription.save()
        
        # Update user profile if subscription is active
        if subscription['status'] == 'active':
            plan_type = get_plan_from_subscription(subscription)
            user_profile = stripe_subscription.user.userprofile
            user_profile.subscription_plan = plan_type
            user_profile.save()
        
        logger.info(f"Updated subscription for user {stripe_subscription.user.username}")
        
    except StripeSubscription.DoesNotExist:
        logger.error(f"StripeSubscription not found: {subscription['id']}")
    except Exception as e:
        logger.error(f"Error handling subscription updated: {str(e)}")


def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    try:
        stripe_subscription = StripeSubscription.objects.get(
            stripe_subscription_id=subscription['id']
        )
        
        # Update subscription status
        stripe_subscription.status = 'canceled'
        stripe_subscription.save()
        
        # Downgrade user to free plan
        user_profile = stripe_subscription.user.userprofile
        user_profile.subscription_plan = 'free'
        user_profile.save()
        
        logger.info(f"Canceled subscription for user {stripe_subscription.user.username}")
        
    except StripeSubscription.DoesNotExist:
        logger.error(f"StripeSubscription not found: {subscription['id']}")
    except Exception as e:
        logger.error(f"Error handling subscription deleted: {str(e)}")


def handle_payment_succeeded(invoice):
    """Handle successful payment"""
    try:
        # Record the payment in our database
        customer_id = invoice['customer']
        stripe_customer = StripeCustomer.objects.get(stripe_customer_id=customer_id)
        
        # Create payment record
        payment = StripePayment.objects.create(
            user=stripe_customer.user,
            stripe_payment_intent_id=invoice['payment_intent'],
            stripe_customer=stripe_customer,
            amount=invoice['amount_paid'] / 100,  # Convert from cents
            currency=invoice['currency'].upper(),
            status='succeeded',
            subscription_plan=stripe_customer.user.userprofile.subscription_plan
        )
        
        logger.info(f"Recorded successful payment for user {stripe_customer.user.username}")
        
    except StripeCustomer.DoesNotExist:
        logger.error(f"StripeCustomer not found for payment: {invoice['id']}")
    except Exception as e:
        logger.error(f"Error handling payment succeeded: {str(e)}")


def handle_payment_failed(invoice):
    """Handle failed payment"""
    try:
        customer_id = invoice['customer']
        stripe_customer = StripeCustomer.objects.get(stripe_customer_id=customer_id)
        
        # Record the failed payment
        payment = StripePayment.objects.create(
            user=stripe_customer.user,
            stripe_payment_intent_id=invoice['payment_intent'],
            stripe_customer=stripe_customer,
            amount=invoice['amount_due'] / 100,  # Convert from cents
            currency=invoice['currency'].upper(),
            status='failed',
            subscription_plan=stripe_customer.user.userprofile.subscription_plan
        )
        
        logger.info(f"Recorded failed payment for user {stripe_customer.user.username}")
        
    except StripeCustomer.DoesNotExist:
        logger.error(f"StripeCustomer not found for failed payment: {invoice['id']}")
    except Exception as e:
        logger.error(f"Error handling payment failed: {str(e)}")


def get_plan_from_subscription(subscription):
    """Extract plan type from Stripe subscription"""
    # Get the price ID from the subscription items
    if subscription['items'] and subscription['items']['data']:
        price_id = subscription['items']['data'][0]['price']['id']
        
        # Map price ID back to plan type
        for plan, configured_price_id in settings.STRIPE_PRICE_IDS.items():
            if configured_price_id == price_id:
                return plan
    
    # Default fallback
    return 'free'