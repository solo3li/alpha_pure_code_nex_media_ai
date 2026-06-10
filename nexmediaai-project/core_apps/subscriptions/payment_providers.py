# payment_providers.py - Clean PayPal Implementation

import requests
import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

class PaymentProvider:
    def process_payment(self, amount, user_id, plan_name, card_details, **kwargs):
        raise NotImplementedError("This method must be implemented by subclasses.")

class PaymobProvider:
    def __init__(self):
        self.secret_key = settings.PAYMOB_SECRET_KEY
        self.public_key = settings.PAYMOB_PUBLIC_KEY
        self.intention_url = "https://accept.paymob.com/v1/intention/"
        self.checkout_url = "https://accept.paymob.com/unifiedcheckout/"
        # Use your configured integration ID(s)
        self.payment_methods = [4928859, 4928858] # or your specific IDs [4928859, 4928858]

    def process_payment(self, amount, user_id, plan_name, card_details=None, **kwargs):
        """Process payment using Paymob's Intention API."""
        try:
            # Convert amount to cents (as required by Paymob)
            amount_cents = int(amount * 100)
            
            payload = {
                "amount": amount_cents,
                "currency": "EGP",
                "payment_methods": self.payment_methods,
                "items": [{
                    "name": plan_name[:50],  # Max 50 characters
                    "amount": amount_cents,  # Amount in cents for this item
                    "description": f"Subscription for {plan_name}"[:255],  # Max 255 characters
                    "quantity": 1,
                }],
                "billing_data": {
                    "apartment": "NA",
                    "first_name": str(user_id)[:50],  # Max 50 characters
                    "last_name": plan_name[:50],  # Max 50 characters  
                    "street": "NA",
                    "building": "NA",
                    "phone_number": "+201553963637",  # Valid phone number format
                    "country": "EG",
                    "email": "ramiadelshawky@mail.com",  # Should use actual user email if available
                    "floor": "5",
                    "state": "cairo",
                    "city": "giza"  # Added missing city field
                },
                # Removed invalid "customer" field - use billing_data instead

                "expiration": 3600,
                # Consider adding these URLs for better callback handling
                # "notification_url": "your_webhook_url_here",
                # "redirection_url": "your_redirect_url_here",
            }

            headers = {
                "Authorization": f"Token {self.secret_key}",  # Fixed: Use "Token" not "Bearer"
                "Content-Type": "application/json",
            }

            response = requests.post(self.intention_url, json=payload, headers=headers)

            if response.status_code == 201:
                intention_data = response.json()
                client_secret = intention_data.get("client_secret")
                
                if not client_secret:
                    return {"error": "No client secret in response", "details": intention_data}, 400
                
                # Build checkout URL as per documentation
                checkout_url = f"{self.checkout_url}?publicKey={self.public_key}&clientSecret={client_secret}"
                
                return {
                    "success": "Payment intention created successfully",
                    "payment_intention_id": intention_data.get("id"),
                    "client_secret": client_secret,
                    "checkout_url": checkout_url,  # Renamed from iframe_url for clarity
                    "intention_data": intention_data  # Optional: include full response for debugging
                }, 200
            else:
                error_details = response.json() if response.content else {"error": "No response content"}
                return {
                    "error": "Failed to create payment intention", 
                    "status_code": response.status_code,
                    "details": error_details
                }, 400

        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {str(e)}"}, 500
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}, 500
# Updated PayPal implementation with guest checkout enabled

class PayPalV2(PaymentProvider):
    """PayPal implementation with guest checkout (Pay with Card option)"""
    
    def __init__(self):
        self.CLIENT_ID = settings.PAYPAL_CLIENT_ID
        self.CLIENT_SECRET = settings.PAYPAL_CLIENT_SECRET
        self.API_BASE = settings.PAYPAL_API_BASE
        self.oauth_url = f"{self.API_BASE}/v1/oauth2/token"
        self.orders_url = f"{self.API_BASE}/v2/checkout/orders"
        
    def get_access_token(self):
        """Get PayPal access token"""
        try:
            response = requests.post(
                self.oauth_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials"},
                auth=(self.CLIENT_ID, self.CLIENT_SECRET),
                timeout=10
            )
            response.raise_for_status()
            return response.json()["access_token"]
        except Exception as e:
            logger.error(f"Failed to get PayPal access token: {e}")
            return None
    
    def create_order(self, amount, plan_name, user_id, user_email=None):
        """Create PayPal order with guest checkout enabled"""
        access_token = self.get_access_token()
        if not access_token:
            return None

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "Prefer": "return=representation"
            }
            
            # Format amount to 2 decimal places
            formatted_amount = f"{amount:.2f}"
            
            # Create order data optimized for guest checkout
            data = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD",
                        "value": formatted_amount
                    },
                    "description": f"Digital Services - {plan_name}",
                    "custom_id": f"{user_id}|{plan_name}",
                    "invoice_id": f"INV-{user_id}-{int(datetime.now().timestamp())}"
                }],
                "application_context": {
                    "brand_name": "NexMedia AI",
                    "locale": "en-US",
                    "landing_page": "NO_PREFERENCE",  # This enables guest checkout
                    "shipping_preference": "NO_SHIPPING",
                    "user_action": "PAY_NOW",
                    "payment_method_preference": "UNRESTRICTED",  # Allow all payment methods
                    "return_url": "https://nexmediaai.com/payment/success/",
                    "cancel_url": "https://nexmediaai.com/payment/failed/"
                }
            }
            
            # For sandbox, use sandbox-specific URLs
            if 'sandbox' in self.API_BASE:
                data["application_context"]["return_url"] = "https://www.sandbox.nexmediaai.com/payment/success/"
                data["application_context"]["cancel_url"] = "https://www.sandbox.nexmediaai.com/payment/failed/"
            
            # Don't include payer information - this is crucial for guest checkout
            # PayPal will show the "Pay with Card" option when no payer email is provided
            
            logger.info(f"Creating PayPal order for ${formatted_amount} with guest checkout - User: {user_id}")
            
            response = requests.post(self.orders_url, headers=headers, json=data, timeout=10)
            
            if response.status_code != 201:
                logger.error(f"PayPal API error: {response.status_code} - {response.text}")
                return None
                
            response.raise_for_status()
            result = response.json()
            logger.info(f"PayPal order created successfully: {result.get('id')}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating PayPal order: {e}")
            return None
    
    def create_guest_checkout_order(self, amount, plan_name, user_id):
        """Create PayPal order specifically optimized for guest checkout"""
        access_token = self.get_access_token()
        if not access_token:
            return None

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "Prefer": "return=representation"
            }
            
            formatted_amount = f"{amount:.2f}"
            
            # Order data optimized for guest checkout (Pay with Card option)
            data = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD",
                        "value": formatted_amount
                    },
                    "description": "Digital Services Subscription",
                    "custom_id": f"{user_id}|{plan_name}",
                    "invoice_id": f"INV-{user_id}-{int(datetime.now().timestamp())}"
                }],
                "application_context": {
                    "brand_name": "NexMedia AI",
                    "locale": "en-US",
                    "landing_page": "NO_PREFERENCE",  # This is key for guest checkout
                    "shipping_preference": "NO_SHIPPING",
                    "user_action": "PAY_NOW",
                    "payment_method_preference": "UNRESTRICTED",  # Allow all payment methods
                    "return_url": "https://nexmediaai.com/payment/success/",
                    "cancel_url": "https://nexmediaai.com/payment/failed/"
                }
            }
            
            # For sandbox, use sandbox-specific URLs
            if 'sandbox' in self.API_BASE:
                data["application_context"]["return_url"] = "https://www.sandbox.nexmediaai.com/payment/success/"
                data["application_context"]["cancel_url"] = "https://www.sandbox.nexmediaai.com/payment/failed/"
            
            logger.info(f"Creating guest checkout order for ${formatted_amount} - User: {user_id}")
            
            response = requests.post(self.orders_url, headers=headers, json=data, timeout=10)
            
            if response.status_code != 201:
                logger.error(f"PayPal API error: {response.status_code} - {response.text}")
                return None
                
            response.raise_for_status()
            result = response.json()
            logger.info(f"Guest checkout order created: {result.get('id')}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating guest checkout order: {e}")
            return None
    
    def create_order_with_advanced_cards(self, amount, plan_name, user_id, user_email=None):
        """Alternative method using Advanced Credit and Debit Card Payments"""
        access_token = self.get_access_token()
        if not access_token:
            return None

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "Prefer": "return=representation",
                "PayPal-Request-Id": f"order_{user_id}_{int(datetime.now().timestamp())}"
            }
            
            formatted_amount = f"{amount:.2f}"
            
            data = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD", 
                        "value": formatted_amount
                    },
                    "description": f"Digital Services - {plan_name}",
                    "custom_id": f"{user_id}|{plan_name}"
                }],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "payment_method_preference": "UNRESTRICTED",
                            "brand_name": "NexMedia AI",
                            "locale": "en-US",
                            "landing_page": "LOGIN",
                            "shipping_preference": "NO_SHIPPING",
                            "user_action": "PAY_NOW"
                        }
                    }
                }
            }
            
            logger.info(f"Creating PayPal order with advanced cards for ${formatted_amount}")
            
            response = requests.post(self.orders_url, headers=headers, json=data, timeout=10)
            
            if response.status_code != 201:
                logger.error(f"PayPal API error: {response.status_code} - {response.text}")
                return None
                
            response.raise_for_status()
            result = response.json()
            logger.info(f"PayPal order with advanced cards created: {result.get('id')}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating PayPal order with advanced cards: {e}")
            return None
    
    def get_order_details(self, order_id):
        """Get PayPal order details"""
        access_token = self.get_access_token()
        if not access_token:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(f"{self.orders_url}/{order_id}", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get PayPal order details: {e}")
            return None
    
    def capture_order(self, order_id):
        """Capture PayPal order"""
        access_token = self.get_access_token()
        if not access_token:
            return {"status": "error", "message": "Authentication failed"}

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "PayPal-Request-Id": f"capture_{order_id}_{int(datetime.now().timestamp())}"
            }
            
            response = requests.post(
                f"{self.orders_url}/{order_id}/capture", 
                headers=headers, 
                json={},
                timeout=15
            )
            
            if response.status_code == 422:
                error_data = response.json()
                logger.warning(f"PayPal compliance violation for order {order_id}: {error_data}")
                
                if 'sandbox' in self.API_BASE:
                    order_details = self.get_order_details(order_id)
                    if order_details and order_details.get('status') == 'APPROVED':
                        logger.info(f"Order {order_id} is still APPROVED despite compliance violation")
                        return {
                            "status": "completed", 
                            "data": order_details,
                            "note": "Sandbox compliance violation bypassed"
                        }
                
                return {
                    "status": "compliance_violation",
                    "error_data": error_data,
                    "message": "Transaction requires manual review"
                }
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"PayPal capture response for {order_id}: {result.get('status')}")
            
            if result.get("status") == "COMPLETED":
                return {"status": "completed", "data": result}
            else:
                return {"status": "pending", "data": result}
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout capturing PayPal order {order_id}")
            return {"status": "timeout", "message": "Request timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error capturing PayPal order {order_id}: {e}")
            return {"status": "error", "message": "Network error"}
        except Exception as e:
            logger.error(f"Unexpected error capturing PayPal order {order_id}: {e}")
            return {"status": "error", "message": "Processing error"}