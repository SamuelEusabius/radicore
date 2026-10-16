from pathlib import Path
from decouple import config, Csv
from datetime import timedelta
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ==========================================================
# SECURITY
# ==========================================================
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-only-do-not-use-in-prod')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())
# ==========================================================
# APPLICATIONS
# ==========================================================
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'allauth',
    'allauth.account',
    'crispy_forms',
    'crispy_tailwind',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.schools',
    'apps.students',
    'apps.teachers',
    'apps.parents',
    'apps.academics',
    'apps.attendance',
    'apps.grades',
    'apps.finance',
    'apps.notifications',
    'apps.dashboard',
    'apps.staff',
    'apps.core',
    'apps.departments',
    'apps.discipline',
    'apps.facilities',
    'apps.events',
    'apps.security',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ==========================================================
# MIDDLEWARE
# ==========================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'apps.schools.middleware.SchoolTenantMiddleware',
    'apps.schools.middleware_subscription.SubscriptionBlockMiddleware',
]

ROOT_URLCONF = 'config.urls'

# ==========================================================
# TEMPLATES
# ==========================================================
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'apps.schools.context_processors.current_school',
            'apps.schools.context_processors.notifications_context',
            'apps.notifications.context_processors.topbar_badge_count',
            'apps.schools.context_processors.enabled_modules',
        ],
    },
}]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ==========================================================
# DATABASE
# ==========================================================
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='sqlite:///db.sqlite3')
    )
}

# ==========================================================
# AUTHENTICATION
# ==========================================================
AUTH_USER_MODEL = 'accounts.User'

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ==================================================
# DJANGO-ALLAUTH SETTINGS
# ==================================================
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'optional'   # prod.py sets 'mandatory'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[ElimuCore] '
ACCOUNT_ADAPTER = 'apps.accounts.adapters.CustomAccountAdapter'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGIN_REDIRECT_URL = '/dashboard/'

# Disable email sending during signup (no SMTP in dev)
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[School MS] '

# Adapter for signup
ACCOUNT_ADAPTER = 'allauth.account.adapter.DefaultAccountAdapter'

ACCOUNT_ADAPTER = 'apps.accounts.adapters.CustomAccountAdapter'
LOGIN_REDIRECT_URL = '/dashboard/'   # fallback
ACCOUNT_LOGIN_REDIRECT_URL = '/dashboard/'

# ==========================================================
# PASSWORD VALIDATORS (relaxed for Kenya school context)
# ==========================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ==========================================================
# REST FRAMEWORK
# ==========================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# ==========================================================
# INTERNATIONALIZATION
# ==========================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# ==========================================================
# STATIC & MEDIA FILES
# ==========================================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================================
# CRISPY FORMS
# ==========================================================
CRISPY_ALLOWED_TEMPLATE_PACKS = 'tailwind'
CRISPY_TEMPLATE_PACK = 'tailwind'

# ==========================================================
# CELERY
# ==========================================================
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# ==========================================================
# EMAIL
# ==========================================================
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='ElimuCore <noreply@elimucore.co.ke>')

# ==========================================================
# PAYMENTS
# ==========================================================
# ==========================================================
# M-PESA DARAJA
# ==========================================================
MPESA_ENV = config('MPESA_ENV', default='sandbox')
MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='')
MPESA_C2B_VALIDATION_URL = config('MPESA_C2B_VALIDATION_URL', default='')
MPESA_C2B_CONFIRMATION_URL = config('MPESA_C2B_CONFIRMATION_URL', default='')

# ==========================================================
# SMS (Africa's Talking)
# ==========================================================
AT_USERNAME = config('AT_USERNAME', default='sandbox')
AT_API_KEY = config('AT_API_KEY', default='')
AT_SENDER_ID = config('AT_SENDER_ID', default='')

# ==========================================================
# APP SETTINGS
# ==========================================================
DEFAULT_CURRENCY = 'KES'
SCHOOL_TRIAL_DAYS = 30
SCHOOL_TRIAL_MAX_STUDENTS = 450
SCHOOL_TRIAL_MAX_TEACHERS = 50