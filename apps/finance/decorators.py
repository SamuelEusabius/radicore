from functools import wraps
from django.http import JsonResponse

# Safaricom production IPs (update if they change)
SAFARICOM_IPS = [
    '196.201.214.200',
    '196.201.214.206',
    '196.201.214.207',
    '196.201.213.114',
    '127.0.0.1', # Added for local testing (remove in production)
]

def verify_mpesa_ip(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded_for:
            ip = forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
            
        if ip not in SAFARICOM_IPS:
            # Return 200 OK to hide rejection from attackers
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Access Denied"}, status=200)
            
        return view_func(request, *args, **kwargs)
    return wrapper