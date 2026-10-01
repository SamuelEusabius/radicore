"""
M-Pesa Daraja API Service — Production Quality

Supports:
  - STK Push (Lipa Na M-Pesa Online)
  - STK Push Query (status polling)
  - C2B (Customer to Business)
  - Access token caching

Docs: https://developer.safaricom.co.ke/docs
"""
import base64
import logging
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://sandbox.safaricom.co.ke"
    if getattr(settings, 'MPESA_ENV', 'sandbox') == 'sandbox'
    else "https://api.safaricom.co.ke"
)


# ==========================================================
# AUTH
# ==========================================================

def get_access_token() -> str:
    """
    Fetch OAuth access token from Safaricom.
    Caches the token for 55 minutes (Safaricom expires at 60 min).
    """
    cached = cache.get('mpesa_access_token')
    if cached:
        return cached

    url = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(
        url,
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=30,
    )
    r.raise_for_status()
    token = r.json()['access_token']

    cache.set('mpesa_access_token', token, timeout=3300)
    logger.info("M-Pesa access token refreshed")
    return token


# ==========================================================
# HELPERS
# ==========================================================

def normalize_phone(phone: str) -> str:
    """
    Convert Kenyan phone numbers to M-Pesa format: 2547XXXXXXXX
    Accepts: 0712345678, 712345678, +254712345678, 254712345678
    """
    if not phone:
        return ''

    p = ''.join(c for c in phone if c.isdigit())

    if p.startswith('254') and len(p) == 12:
        return p
    if p.startswith('0') and len(p) == 10:
        return '254' + p[1:]
    if len(p) == 9 and (p.startswith('7') or p.startswith('1')):
        return '254' + p

    return p


def _timestamp() -> str:
    """Current timestamp in M-Pesa format: YYYYMMDDHHmmss"""
    return datetime.now().strftime('%Y%m%d%H%M%S')


def _password(timestamp: str) -> str:
    """STK Push password: base64(shortcode + passkey + timestamp)"""
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(raw.encode()).decode()


# ==========================================================
# STK PUSH
# ==========================================================

def stk_push(phone: str, amount: float, account_reference: str,
             description: str = "School Fees") -> dict:
    """
    Initiate STK Push (Lipa Na M-Pesa Online).

    Args:
        phone: any common format (0712345678, +254712..., 254712...)
        amount: KES amount (int)
        account_reference: identifier shown on phone (e.g. "INV123")
        description: short description

    Returns:
        Safaricom response dict:
        {
          "MerchantRequestID": "...",
          "CheckoutRequestID": "...",
          "ResponseCode": "0",
          "ResponseDescription": "Success. Request accepted for processing",
          "CustomerMessage": "Success. Request accepted for processing"
        }

    Raises:
        requests.HTTPError on network/API errors
    """
    phone = normalize_phone(phone)
    if not phone:
        raise ValueError("Invalid phone number")

    token = get_access_token()
    ts = _timestamp()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": _password(ts),
        "Timestamp": ts,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(float(amount)),
        "PartyA": phone,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference[:12],
        "TransactionDesc": description[:100],
    }

    url = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {token}"}

    logger.info(f"STK Push → {phone} KES {amount} ref={account_reference}")
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    result = r.json()
    logger.info(f"STK Push response: {result}")
    return result


def stk_query(checkout_request_id: str) -> dict:
    """
    Query the status of an STK Push request.

    Returns Safaricom response with ResultCode and details.
    """
    token = get_access_token()
    ts = _timestamp()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": _password(ts),
        "Timestamp": ts,
        "CheckoutRequestID": checkout_request_id,
    }

    url = f"{BASE_URL}/mpesa/stkpushquery/v1/query"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


# ==========================================================
# C2B
# ==========================================================

def register_c2b_urls() -> dict:
    """
    Register C2B validation + confirmation URLs with Safaricom.
    Call once per shortcode. Safe to call multiple times.
    """
    token = get_access_token()

    payload = {
        "ShortCode": settings.MPESA_SHORTCODE,
        "ResponseType": "Completed",
        "ConfirmationURL": settings.MPESA_C2B_CONFIRMATION_URL,
        "ValidationURL": settings.MPESA_C2B_VALIDATION_URL,
    }

    url = f"{BASE_URL}/mpesa/c2b/v1/registerurl"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def simulate_c2b(phone: str, amount: float, bill_ref: str) -> dict:
    """
    Sandbox-only: simulate a C2B payment (as if parent paid via paybill).
    Not available in production.
    """
    token = get_access_token()

    payload = {
        "ShortCode": settings.MPESA_SHORTCODE,
        "CommandID": "CustomerPayBillOnline",
        "Amount": int(amount),
        "Msisdn": normalize_phone(phone),
        "BillRefNumber": bill_ref,
    }

    url = f"{BASE_URL}/mpesa/c2b/v1/simulate"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()