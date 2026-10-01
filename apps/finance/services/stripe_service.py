import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(invoice, success_url, cancel_url):
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'kes',
                'product_data': {'name': f'Invoice #{invoice.id} School Fees'},
                'unit_amount': int(invoice.balance * 100),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={'invoice_id': invoice.id},
    )
    return session.url