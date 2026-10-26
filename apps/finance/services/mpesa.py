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

def stk_push(phone, amount, account_reference=None, description="Payment", **kwargs):
    """
    Universal STK Push.
    Accepts dynamic shortcodes and keys for multi-tenant SaaS routing.
    """
    import requests
    import base64
    from datetime import datetime
    from django.conf import settings
    
    # 1. Get Credentials securely (strip hidden spaces that cause 400 errors)
    consumer_key = (kwargs.get('consumer_key') or settings.MPESA_CONSUMER_KEY or '').strip()
    consumer_secret = (kwargs.get('consumer_secret') or settings.MPESA_CONSUMER_SECRET or '').strip()
    shortcode = (kwargs.get('shortcode') or settings.MPESA_SHORTCODE or '').strip()
    passkey = (kwargs.get('passkey') or settings.MPESA_PASSKEY or '').strip()
    callback_url = kwargs.get('callback_url') or settings.MPESA_CALLBACK_URL
    
    # Support both `account_ref` and `account_reference`
    account_ref = kwargs.get('account_ref') or account_reference or "Payment"

    if not consumer_key or not consumer_secret:
        return {"error": "Consumer Key or Secret is completely empty. Check settings."}

    # 2. Determine Environment (Sandbox vs Production)
    # Defaults to sandbox unless explicitly set to production in .env
    env = getattr(settings, 'MPESA_ENV', 'sandbox').lower()
    api_url = "https://sandbox.safaricom.co.ke" if env == 'sandbox' else "https://api.safaricom.co.ke"
    
    # 3. Get OAuth Token
    auth_url = f"{api_url}/oauth/v1/generate?grant_type=client_credentials"
    try:
        auth_res = requests.get(auth_url, auth=(consumer_key, consumer_secret))
        
        if auth_res.status_code != 200:
            return {"error": f"Safaricom Auth Error (Code {auth_res.status_code}): {auth_res.text}"}
            
        access_token = auth_res.json().get('access_token')
    except Exception as e:
        return {"error": f"Auth failed: {str(e)}"}

    if not access_token:
        return {"error": "Failed to get access token. Check Daraja credentials."}

    # 4. Prepare STK Push Payload
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password_str = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(password_str.encode()).decode()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Format phone (254...)
    phone_str = str(phone).strip()
    if phone_str.startswith('0'):
        phone_str = '254' + phone_str[1:]
    elif phone_str.startswith('+'):
        phone_str = phone_str[1:]

    # Determine Transaction Type (Paybill vs Till)
    tx_type = "CustomerPayBillOnline"
    if kwargs.get('account_type') == 'till':
        tx_type = "CustomerBuyGoodsOnline"

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": tx_type,
        "Amount": int(float(amount)),
        "PartyA": phone_str,
        "PartyB": shortcode,
        "PhoneNumber": phone_str,
        "CallBackURL": callback_url,
        "AccountReference": account_ref,
        "TransactionDesc": description
    }

    # 5. Send Request
    stk_url = f"{api_url}/mpesa/stkpush/v1/processrequest"
    try:
        res = requests.post(stk_url, json=payload, headers=headers)
        # Return the JSON response from Safaricom
        return res.json()
    except Exception as e:
        return {"error": f"STK Push failed: {str(e)}"}

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