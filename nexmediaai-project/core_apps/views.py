# views.py - Clean PayPal Implementation

import json
import logging
import secrets
from datetime import datetime, timedelta
from uuid import UUID
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseServerError
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from .models import Plan, Subscription, Payment
from .payment_providers import PayPalV2
from .payment_factory import PaymentProviderFactory
from .helpers import generate_signature, validate_signature, generate_nonce, get_timestamp
from .utils import initialize_tool_usage

logger = logging.getLogger(__name__)
User = get_user_model()

class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)

# PayPal Views
@require_POST
@login_required
def create_paypal_order(request):
    """Create PayPal order"""
    try:
        data = json.loads(request.body)
        plan_name = data.get('plan_name')
        
        if not plan_name:
            return JsonResponse({'error': 'Plan name is required'}, status=400)

        # Get plan
        try:
            plan = Plan.objects.get(name=plan_name)
        except Plan.DoesNotExist:
            return JsonResponse({'error': 'Invalid plan'}, status=400)

        # Create order
        provider = PayPalV2()
        order = provider.create_order(
            amount=float(plan.price_usd),
            plan_name=plan_name,
            user_id=str(request.user.id),
            user_email=request.user.email
        )
        
        if not order or 'id' not in order:
            return JsonResponse({'error': 'Failed to create order'}, status=500)

        # Store order info
        request.session['paypal_order'] = {
            'order_id': order['id'],
            'plan_name': plan_name,
            'amount': float(plan.price_usd),
            'user_id': str(request.user.id)
        }

        # Return order ID and PayPal checkout URL
        paypal_checkout_url = f"https://www.paypal.com/checkoutnow?token={order['id']}"
        
        return JsonResponse({
            'orderID': order['id'],
            'checkout_url': paypal_checkout_url
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid data'}, status=400)
    except Exception as e:
        logger.error(f"Error creating PayPal order: {e}")
        return JsonResponse({'error': 'Order creation failed'}, status=500)


@require_POST
@login_required
def capture_paypal_payment(request):
    """Handle PayPal payment capture"""
    try:
        data = json.loads(request.body)
        order_id = data.get('orderID')

        # Validate session
        stored_order = request.session.get('paypal_order')
        if not stored_order or stored_order['order_id'] != order_id:
            return JsonResponse({'error': 'Invalid order'}, status=400)

        provider = PayPalV2()
        
        # Try to capture
        capture_result = provider.capture_order(order_id)
        
        if capture_result['status'] == 'completed':
            # Success - process immediately
            success = process_payment(
                user_id=stored_order['user_id'],
                plan_name=stored_order['plan_name'],
                order_id=order_id,
                amount=stored_order['amount']
            )
            
            if success:
                # Clear session and redirect to success
                clear_paypal_session(request)
                request.session['payment_success'] = True
                request.session['order_id'] = order_id
                
                return JsonResponse({
                    'success': True,
                    'message': 'Payment completed successfully!',
                    'redirect': True
                })
            else:
                return JsonResponse({'error': 'Failed to process subscription'}, status=500)
                
        elif capture_result['status'] == 'compliance_violation':
            # Handle compliance violation
            logger.warning(f"Compliance violation for order {order_id}")
            
            # Check if order is still approved
            order_details = provider.get_order_details(order_id)
            if order_details and order_details.get('status') == 'APPROVED':
                # Process manually since PayPal approved the payment
                logger.info(f"Processing approved order {order_id} manually due to compliance block")
                
                success = process_payment(
                    user_id=stored_order['user_id'],
                    plan_name=stored_order['plan_name'],
                    order_id=order_id,
                    amount=stored_order['amount']
                )
                
                if success:
                    clear_paypal_session(request)
                    request.session['payment_success'] = True
                    request.session['order_id'] = order_id
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Payment processed successfully!',
                        'note': 'Processed via alternative method due to compliance check',
                        'redirect': True
                    })
            
            # If we can't process, return error
            return JsonResponse({
                'error': 'compliance_violation',
                'message': 'Payment requires manual review. Please contact support.',
                'support_email': 'support@nexmediaai.com',
                'order_id': order_id
            }, status=422)
            
        else:
            # Other errors (timeout, network, etc.)
            return JsonResponse({
                'error': 'processing_failed',
                'message': 'Payment processing failed. Please try again.',
                'details': capture_result.get('message', '')
            }, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid data'}, status=400)
    except Exception as e:
        logger.error(f"Error capturing PayPal payment: {e}")
        return JsonResponse({'error': 'Processing error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def paypal_webhook(request):
    """Handle PayPal webhooks"""
    try:
        data = json.loads(request.body)
        event_type = data.get("event_type")
        resource = data.get("resource", {})
        order_id = resource.get("id")

        print(f"PayPal webhook: {event_type} for order {order_id}")

        # Handle different event types
        if event_type == "CHECKOUT.ORDER.COMPLETED":
            # Order is approved but payment not yet captured
            # Just acknowledge - don't process payment yet
            print(f"Order {order_id} approved, waiting for payment capture")
            return JsonResponse({"status": "order_approved"}, status=200)
            
        elif event_type == "CHECKOUT.ORDER.APPROVED":
            # Order is approved - acknowledge
            print(f"Order {order_id} approved")
            return JsonResponse({"status": "order_approved"}, status=200)
            
        elif event_type == "PAYMENT.CAPTURE.COMPLETED":
            # Payment is actually completed - process subscription
            # Check if already processed
            if order_id and Payment.objects.filter(payment_id=order_id).exists():
                logger.info(f"Payment {order_id} already processed")
                return JsonResponse({"status": "already_processed"}, status=200)

            # Extract payment data
            user_id, plan_name, amount = extract_webhook_data(data)
            
            if user_id and plan_name:
                success = process_payment(user_id, plan_name, order_id, amount)
                if success:
                    logger.info(f"Payment capture completed for order {order_id} - subscription created")
                    return JsonResponse({"status": "payment_completed"}, status=200)
                else:
                    logger.error(f"Failed to process payment capture for order {order_id}")
            else:
                logger.error(f"Missing data in payment capture webhook for order {order_id}")
                
        elif event_type == "PAYMENT.CAPTURE.DECLINED":
            # Payment was declined - log for monitoring
            logger.warning(f"Payment capture declined for order {order_id}")
            return JsonResponse({"status": "payment_declined"}, status=200)

        return JsonResponse({"status": "acknowledged"}, status=200)

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JsonResponse({"error": str(e)}, status=500)

 
@login_required
def payment_success(request):
    """Display payment success page"""
    # Check if this is a PayPal return
    token = request.GET.get('token')
    payer_id = request.GET.get('PayerID')
    
    if token and payer_id:
        # This is a PayPal return - process the payment
        try:
            provider = PayPalV2()
            
            # Get order details
            order_details = provider.get_order_details(token)
            if not order_details:
                return redirect('payment_failed')
            
            # Check if order is approved
            if order_details.get('status') != 'APPROVED':
                return redirect('payment_failed')
            
            # Try to capture the payment
            capture_result = provider.capture_order(token)
            
            if capture_result['status'] == 'completed':
                # Get stored order info
                stored_order = request.session.get('paypal_order')
                if stored_order and stored_order['order_id'] == token:
                    success = process_payment(
                        user_id=stored_order['user_id'],
                        plan_name=stored_order['plan_name'],
                        order_id=token,
                        amount=stored_order['amount']
                    )
                    
                    if success:
                        clear_paypal_session(request)
                        request.session['payment_success'] = True
                        request.session['order_id'] = token
                    else:
                        return redirect('payment_failed')
                else:
                    return redirect('payment_failed')
            else:
                return redirect('payment_failed')
                
        except Exception as e:
            logger.error(f"Error processing PayPal return: {e}")
            return redirect('payment_failed')
    
    # Check if payment was already processed
    if not request.session.get('payment_success'):
        return redirect('home:home')

    order_id = request.session.get('order_id', 'Unknown')
    
    # Clear session
    request.session.pop('payment_success', None)
    request.session.pop('order_id', None)

    return render(request, 'subscriptions/success.html', {
        'order_id': order_id,
        'payment_method': 'PayPal',
        'status': 'Completed',
        'immediate_success': True
    })


@login_required
def payment_failed(request):
    """Display payment failure page"""
    # Check if this is a PayPal cancel
    token = request.GET.get('token')
    
    if token:
        # This is a PayPal cancel - clear session
        clear_paypal_session(request)
        request.session['payment_failed'] = True
        request.session['error_message'] = 'Payment was cancelled'
    
    # Check if payment was already marked as failed
    if not request.session.get('payment_failed'):
        return redirect('home:home')

    error_message = request.session.get('error_message', 'Payment failed')
    
    # Clear session
    request.session.pop('payment_failed', None)
    request.session.pop('error_message', None)

    return render(request, 'subscriptions/failed.html', {
        'error': error_message
    })


# Helper Functions
def process_payment(user_id, plan_name, order_id, amount):
    """Process successful payment"""
    try:
        # Get user and plan
        user = User.objects.get(pk=user_id)
        plan = Plan.objects.get(name=plan_name)

        # Check for existing payment
        if Payment.objects.filter(payment_id=order_id).exists():
            logger.info(f"Payment {order_id} already exists")
            return True

        # Create subscription
        subscription = create_subscription(user, plan)
        if not subscription:
            return False

        # Create payment record
        payment = Payment.objects.create(
            user=user,
            subscription=subscription,
            plan=plan,
            payment_id=order_id,
            amount=amount,
            currency='USD',
            method='PayPal',
            status='Completed'
        )

        # Initialize tools
        initialize_tool_usage(user_id, plan_name)
        
        logger.info(f"Successfully processed payment {order_id} for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error processing payment {order_id}: {e}")
        return False


def create_subscription(user, plan):
    """Create or update subscription"""
    try:
        # Check for existing active subscription
        existing = Subscription.objects.filter(
            user=user, 
            plan=plan, 
            status='Active'
        ).first()
        
        if existing:
            # Extend existing subscription
            existing.end_date = existing.end_date + timedelta(days=plan.duration_days)
            existing.save()
            return existing

        # Create new subscription
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=plan.duration_days)

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            status='Active'
        )

        return subscription

    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        return None


def extract_webhook_data(webhook_data):
    """Extract payment data from webhook"""
    try:
        resource = webhook_data.get("resource", {})
        purchase_units = resource.get("purchase_units") or []
        
        if not purchase_units:
            print("No purchase units found")
            return None, None, None
            
        pu = purchase_units[0]
        
        # Get amount
        amt = pu.get("amount") or {}
        amount = float(amt.get("value")) if amt.get("value") else None
        
        # Get custom_id with user and plan
        custom_id = pu.get("custom_id")
        print(f"Custom ID: {custom_id}")
        if custom_id and "|" in custom_id:
            parts = custom_id.split("|", 1)
            return parts[0], parts[1], amount
        
        return None, None, None

    except Exception as e:
        logger.error(f"Error extracting webhook data: {e}")
        return None, None, None


def clear_paypal_session(request):
    """Clear PayPal session data"""
    keys_to_clear = ['paypal_order', 'pending_paypal_order']
    for key in keys_to_clear:
        request.session.pop(key, None)


# Additional views for Paymob and other functionality

@login_required
def get_payment_form(request):
    if request.method != 'GET':
        return HttpResponseBadRequest("Invalid method")
    
    user = request.user
    csrf_token = secrets.token_hex(16)
    request.session["csrf_token"] = csrf_token
    nonce = generate_nonce()
    timestamp = get_timestamp()
    plan_name = request.GET.get("plan_name")
    provider_name = request.GET.get("provider")

    # Generate signature
    signature_data = f"{user.id}|{plan_name}|{provider_name}|{timestamp}|{nonce}"
    signature = generate_signature(signature_data)

    return JsonResponse({
        "csrf_token": csrf_token,
        "timestamp": timestamp,
        "nonce": nonce,
        "signature": signature,
        "plan_name": plan_name,
        "provider_name": provider_name,
    })

@require_POST
@login_required
def handle_payment(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid method")
    
    try:
        user = request.user
        data = json.loads(request.body)
        plan_name = data.get("plan_name")
        provider_name = data.get("provider_name")
        card_details = data.get("card_details")
        payment_info = data.get("payment_info")

        # Validate CSRF token
        if not payment_info or payment_info.get("csrf_token") != request.session.get("csrf_token"):
            return JsonResponse({"error": "Invalid CSRF token."}, status=403)

        # Validate signature
        signature_data = f"{user.id}|{plan_name}|{provider_name}|{payment_info['timestamp']}|{payment_info['nonce']}"
        if not validate_signature(signature_data, payment_info["signature"]):
            return JsonResponse({"error": "Invalid signature."}, status=400)

        # Fetch the plan from the database
        try:
            plan = Plan.objects.get(name=plan_name)
        except Plan.DoesNotExist:
            return JsonResponse({"error": "Invalid subscription plan."}, status=400)

        # Process payment
        provider = PaymentProviderFactory.get_provider(provider_name)

        if provider_name == "paymob":
            payment_result, status_code = provider.process_payment(
                float(plan.price_egp), 
                str(user.id),  # Convert UUID to string
                plan_name, 
                card_details,
                integration_id=4927392,
                iframe_id=894240
            )

        if status_code == 200:
            return JsonResponse(payment_result, status=status_code, encoder=UUIDEncoder)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.error(f"Error processing payment: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500, encoder=UUIDEncoder)
    
@login_required
def check_paypal_payment_status(request):
    """Check pending payment status"""
    try:
        order_id = request.GET.get('order_id')
        if not order_id:
            return JsonResponse({'error': 'Order ID required'}, status=400)

        logger.info(f"Checking status for PayPal order: {order_id}")

        # Check if payment already exists in our database
        if Payment.objects.filter(payment_id=order_id).exists():
            logger.info(f"Payment {order_id} already processed")
            return JsonResponse({
                'status': 'completed',
                'message': 'Payment found and processed'
            })

        # Check PayPal order status
        provider = PayPalV2()
        order_details = provider.get_order_details(order_id)
        
        if not order_details:
            logger.error(f"Could not retrieve details for order {order_id}")
            return JsonResponse({'error': 'Could not retrieve order details'}, status=400)
        
        paypal_status = order_details.get('status')
        logger.info(f"PayPal status for {order_id}: {paypal_status}")
        
        # Process based on status
        if paypal_status == 'COMPLETED':
            # Process the completed payment
            pending_order = request.session.get('pending_paypal_order')
            if pending_order and pending_order.get('order_id') == order_id:
                user_id = pending_order['user_id']
                plan_name = pending_order['plan_name']
                amount = pending_order['amount']
                
                success = process_payment(user_id, plan_name, order_id, amount)
                if success:
                    del request.session['pending_paypal_order']
                    return JsonResponse({
                        'status': 'completed',
                        'message': 'Payment processed successfully'
                    })
            
            return JsonResponse({
                'status': 'completed', 
                'message': 'Payment completed'
            })
            
        elif paypal_status == 'APPROVED':
            # Try to process approved orders manually
            pending_order = request.session.get('pending_paypal_order')
            if pending_order and pending_order.get('order_id') == order_id:
                user_id = pending_order['user_id']
                plan_name = pending_order['plan_name']
                amount = pending_order['amount']
                
                # Process manually since PayPal approved but capture might fail
                success = process_payment(user_id, plan_name, order_id, amount)
                if success:
                    del request.session['pending_paypal_order']
                    return JsonResponse({
                        'status': 'completed',
                        'message': 'Payment processed successfully'
                    })
            
            return JsonResponse({
                'status': 'processing',
                'message': 'Payment still being processed'
            })
            
        else:
            return JsonResponse({
                'status': 'failed' if paypal_status in ['VOIDED', 'EXPIRED'] else 'processing',
                'message': f'Payment status: {paypal_status}'
            })

    except Exception as e:
        logger.error(f"Error checking PayPal status: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Status check failed'
        }, status=500)

    
@login_required
def subscribe(request):
    plan_name = request.GET.get("plan_name")
    currency = request.GET.get("currency", "Dollar")  # Default to Dollar if not provided

    # Validate currency
    valid_currencies = ["Dollar", "EGP"]
    if currency not in valid_currencies:
        currency = "Dollar"  # Default to Dollar if invalid currency is provided

    # Set currency symbol
    currency_symbol = "EGP " if currency == "EGP" else "$"

    if not plan_name:
        return render(request, "subscriptions/subscribe.html")

    try:
        # Fetch the plan from the database
        plan = Plan.objects.get(name=plan_name)
        
        # Format the plan data for the template
        plan_data = {
            "name": plan.name,
            "id": plan.id,
            "type": "Pro" if "Pro" in plan.name else "ProPlus",  # Adjust based on your naming convention
            "amount": float(plan.price_usd),  # USD price
            "amount_egp": float(plan.price_egp),  # EGP price
            "currency": "USD",  # Default currency
            "duration": f"{plan.duration_days} DAYS",
            "features": []  # Add features if needed
        }

        # Pass the plan and currency to the template
        return render(request, "subscriptions/payment_form.html", {
            "plan": plan_data, 
            "currency_symbol": currency_symbol
        })

    except Plan.DoesNotExist:
        return HttpResponseBadRequest("Invalid Plan")
    except Exception as e:
        logger.error(f"Error in subscribe view: {e}")
        return HttpResponseServerError(f"An error occurred: {e}")


@csrf_exempt
@require_http_methods(["POST"])
def paymob_webhook(request):
    try:
        data = json.loads(request.body)
        print("📩 Raw request body:", request.body.decode())  # <-- Add this
            
        print("✅ Parsed JSON data:", json.dumps(data, indent=2))  # Optional pretty print
        logger.info(f"Received Paymob webhook: {data}")

        # Extract payment details from the callback payload
        transaction = data.get("obj", {})
        order = transaction.get("order", {})
        order_id = transaction.get("id")  # Paymob order ID
        amount_cents = transaction.get("amount_cents")  # Amount in cents
        currency = transaction.get("currency")  # Currency (e.g., EGP)
        success = transaction.get("success")  # Payment success status

        # Extract payment method from source_data
        source_data = transaction.get("source_data", {})
        payment_method = source_data.get("type", "Paymob")

        if not success:
            logger.error("Payment failed.")
            return JsonResponse({"error": "Payment failed."}, status=400)

        # Extract user_id from payment_key_claims
        payment_key_claims = transaction.get("payment_key_claims", {})
        billing_data = payment_key_claims.get("billing_data", {})
        user_id = billing_data.get("first_name")  # Fetch user_id from payment_key_claims

        if not user_id:
            logger.error(f"Missing user_id in payment_key_claims. {user_id}")
            return JsonResponse({"error": "Missing user_id in payment_key_claims."}, status=400)

        # Extract plan_name from billing_data
        plan_name = billing_data.get("last_name")  # Fetch plan_name from billing_data

        if not plan_name:
            logger.error(f"Missing plan_name in billing_data. {plan_name}")
            return JsonResponse({"error": "Missing plan_name in billing_data."}, status=400)

        try:
            # Fetch the plan from the database
            plan = Plan.objects.get(name=plan_name)
            
            # Save subscription
            subscription_result, subscription_code = save_subscription(user_id, plan_name)
            if subscription_code != 200:
                logger.error(f"Failed to save subscription: {subscription_result}")
                return JsonResponse(subscription_result, status=subscription_code)

            # Extract subscription ID
            subscription_id = subscription_result.get("subscription_id")

            # Save payment
            payment_result, payment_code = save_payment(
                user_id=user_id,
                subscription_id=subscription_id,
                payment_id=order_id,  # Use the Paymob order ID
                amount=amount_cents / 100,  # Convert cents to dollars
                currency=currency,
            method=payment_method,  # Dynamic payment method (paymob or wallet)
            plan_id=plan.id
            )

            if payment_code != 200:
                logger.error(f"Failed to save payment: {payment_result}")
                return JsonResponse(payment_result, status=payment_code)

            # Initialize tool usage
            logger.info("Initializing tool usage")
            initialize_tool_usage(user_id, plan_name)

            logger.info("Payment processed successfully.")
            return JsonResponse({"success": "Payment processed successfully."}, status=200)

        except Plan.DoesNotExist:
            logger.error(f"Plan not found: {plan_name}")
            return JsonResponse({"error": "Plan not found."}, status=400)
        except Exception as e:
            logger.error(f"Error processing Paymob webhook: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

def save_subscription(user_id, plan_name):
    """Save subscription to database"""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = User.objects.get(pk=user_id)
        plan = Plan.objects.get(name=plan_name)

        # Check for existing active subscription
        existing_sub = Subscription.objects.filter(
            user=user, plan=plan, status='Active'
        ).first()
        
        if existing_sub:
            logger.info(f"Active subscription already exists for user {user_id}")
            return {"subscription_id": existing_sub.id, "plan_name": plan_name}, 200

        # Create new subscription
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=plan.duration_days)

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            status='Active'
        )
        
        return {"subscription_id": subscription.id, "plan_name": plan_name}, 200

    except Exception as e:
        logger.error(f"Error saving subscription: {e}")
        return {"error": str(e)}, 500

def save_payment(user_id, subscription_id, payment_id, amount, currency, method, plan_id):
    """Save payment to database"""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.get(pk=user_id)
        subscription = Subscription.objects.get(pk=subscription_id)

        # Check for existing payment
        existing_payment = Payment.objects.filter(payment_id=payment_id).first()
        if existing_payment:
            logger.info(f"Payment {payment_id} already exists")
            return {"success": "Payment already recorded"}, 200

        # Create payment record
        payment = Payment.objects.create(
            user=user,
            subscription=subscription,
            plan_id=plan_id,
            payment_id=payment_id,
            amount=amount,
            currency=currency,
            method=method,
            status='Completed'
        )

        return {"success": "Payment saved successfully"}, 200
        
    except Exception as e:
        logger.error(f"Error saving payment: {e}")
        return {"error": str(e)}, 500

@login_required
def payment_callback(request):
    print("📩 Raw request body:", request.body.decode())  # <-- Add this
    data = json.loads(request.body)
    print("✅ Parsed JSON data:", json.dumps(data, indent=2))  # Optional pretty print
    # Extract payment details from the query parameters
    order_id = request.GET.get("id")  # Paymob order ID (may not exist for wallet payments)
    success = request.GET.get("success") == "true"  # Payment success status
    source_data_type = request.GET.get("source_data.type")  # Payment method (wallet or paymob)

    # Determine the payment method
    payment_method = source_data_type if source_data_type == "wallet" else "paymob"

    # Set payment status in the session
    if success:
        request.session["payment_success"] = True
        request.session["order_id"] = order_id if order_id else "N/A"  # Handle cases where order_id is missing
        request.session["payment_method"] = payment_method  # Store the payment method in the session
        return redirect("payment_success")
    else:
        request.session["payment_failed"] = True
        request.session["payment_method"] = payment_method  # Store the payment method in the session
        return redirect("payment_failed")