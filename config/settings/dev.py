"""
Development settings. Safe defaults, zero setup required.
"""
from .base import *
from decouple import config
import dj_database_url
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# Since this file is in config/settings/dev.py, BASE_DIR needs to go up 3 levels.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEBUG = True
ALLOWED_HOSTS = ['*']

# If DATABASE_URL is set (e.g., Docker Postgres), use it.
# Otherwise fall back to SQLite for zero-setup dev.
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='sqlite:///db.sqlite3'),
        conn_max_age=0,
    )
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
ACCOUNT_EMAIL_VERIFICATION = 'none'   # dev convenience

# ==========================================================
# STATIC FILES (Required for images, CSS, JS to load in dev)
# ==========================================================
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Media files (Uploads from users)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

# Optional SQL logging: set DEBUG_SQL=True in .env
if config('DEBUG_SQL', default=False, cast=bool):
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {'class': 'logging.StreamHandler'},
        },
        'loggers': {
            'django.db.backends': {
                'handlers': ['console'],
                'level': 'DEBUG',
            },
        },
    }
    # ==========================================================
# CLOUDFLARE TUNNEL / CSRF FIX
# ==========================================================
CSRF_TRUSTED_ORIGINS = [
    'https://*.trycloudflare.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# ==========================================================
# SILENCE XHTML2PDF CSS WARNINGS
# ==========================================================
import logging
logging.getLogger("xhtml2pdf").setLevel(logging.ERROR)