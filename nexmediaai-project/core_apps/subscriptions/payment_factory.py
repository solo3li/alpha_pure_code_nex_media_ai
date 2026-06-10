from .payment_providers import  PaymobProvider, PayPalV2

class PaymentProviderFactory:
    providers = {
        # "paypal": PayPalProvider(),
        "paymob": PaymobProvider(),
        # "wallet": WalletProvider(),
        "paypalv2": PayPalV2(),
    }

    @staticmethod
    def get_provider(provider_name):
        """Get a payment provider by name."""
        provider = PaymentProviderFactory.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Payment provider {provider_name} is not supported.")
        return provider