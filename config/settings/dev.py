"""
Development settings. Safe defaults, zero setup required.
"""
from .base import *
from decouple import config
import dj_database_url

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