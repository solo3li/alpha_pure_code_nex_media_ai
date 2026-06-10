from django.urls import path
from . import views

urlpatterns = [
    path("create-paypal-order/", views.create_paypal_order, name="create_paypal_order"),
    path("capture-paypal-payment/", views.capture_paypal_payment, name="capture_paypal_payment"),
    path("get-payment-form/", views.get_payment_form, name="get_payment_form"),
    
    path("pay/", views.handle_payment, name="handle_payment"),
    path("subscribe/", views.subscribe, name="subscribe"),
    
    path("paymob-webhook/", views.paymob_webhook, name="paymob_webhook"),
    path("paypal-webhook/", views.paypal_webhook, name="paypal_webhook"),
    path("payment/callback/", views.payment_callback, name="payment_callback"),

    path("payment/success/", views.payment_success, name="payment_success"),
    path("payment/failed/", views.payment_failed, name="payment_failed"),
    path("check-paypal-status/", views.check_paypal_payment_status, name="check_paypal_status"),

]