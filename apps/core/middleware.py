import hashlib
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib.auth import logout


class SecureSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Skip middleware for static files, media, and the login page
        if (request.path.startswith('/static/') or 
            request.path.startswith('/media/') or 
            request.path.startswith('/accounts/login') or
            request.path == '/login/' or 
            request.path == '/'):
            response = self.get_response(request)
            # Attach cookie if a new session was just created during login
            raw_key = getattr(request, '_rc_raw_session_key', None)
            if raw_key:
                response.set_cookie(
                    'rc_session_key', raw_key,
                    httponly=True, secure=False, samesite='Lax',
                    max_age=60 * 60 * 24 * 30
                )
            return response

        # 2. Get the raw key from the HttpOnly cookie
        raw_key = request.COOKIES.get('rc_session_key')
        
        if not raw_key:
            return self.get_response(request)

        # 3. Hash the raw key to look it up in the DB
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        try:
            from apps.accounts.models import UserSession
            session = UserSession.objects.get(key_hash=key_hash, is_active=True)
            
            # 4. IP & DEVICE BINDING CHECK
            current_ip = request.META.get('REMOTE_ADDR')
            current_device = request.META.get('HTTP_USER_AGENT', 'Unknown')[:255]

            if not current_ip or session.ip_address != current_ip or session.device != current_device:
                session.is_active = False
                session.save()
                logout(request)
                response = redirect('/accounts/login/')
                response.delete_cookie('rc_session_key')
                return response

            # 5. Attach user
            request.user = session.user
            request.secure_session = session
            session.save()

        except Exception:
            logout(request)
            response = redirect('/accounts/login/')
            response.delete_cookie('rc_session_key')
            return response

        response = self.get_response(request)
        
        # Attach cookie if a new session was just created (post-login)
        raw_key_new = getattr(request, '_rc_raw_session_key', None)
        if raw_key_new:
            response.set_cookie(
                'rc_session_key', raw_key_new,
                httponly=True, secure=False, samesite='Lax',
                max_age=60 * 60 * 24 * 30
            )
        
        return response