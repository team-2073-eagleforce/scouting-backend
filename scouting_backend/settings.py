"""
Django settings for scouting_backend project.
"""
import os
import secrets
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv


load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 1. The URL used when referring to static files
STATIC_URL = 'static/'

# 2. Locations of static files during development
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# 3. The folder where collectstatic will put files for production
STATIC_ROOT = BASE_DIR / "staticfiles"

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', '').strip()
_debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
if not SECRET_KEY:
    if not _debug_mode:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "SECRET_KEY environment variable must be set in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(50))\""
        )
    SECRET_KEY = secrets.token_urlsafe(50)
    import warnings
    warnings.warn(
        "No SECRET_KEY set — using a temporary key for development. "
        "Sessions will not persist across restarts.",
        stacklevel=2,
    )

# Set DEBUG based on environment
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    "scouting.chrisccluk.live",
    "scout.chrisccluk.live",
]

# IPs allowed to set X-Forwarded-For (e.g. Render's load balancer, nginx)
TRUSTED_PROXIES = os.environ.get('TRUSTED_PROXIES', '').split(',')
TRUSTED_PROXIES = [ip.strip() for ip in TRUSTED_PROXIES if ip.strip()]

# CSRF configuration
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'https://localhost:8000',
    'http://127.0.0.1:8000',
    'https://scouting.chrisccluk.live',
    'https://scout.chrisccluk.live',
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    "crispy_bootstrap4",
    'scouting_backend',
    'teams',
    'strategy',
    'authenticate',
    'scanner',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'scouting_backend.middleware.plugin_injection.PluginInjectionMiddleware',
]

ROOT_URLCONF = 'scouting_backend.urls'

UI_TEMPLATES = [
    os.path.join(BASE_DIR, 'templates'),
    os.path.join('scanner', 'templates', 'scanner'),
    os.path.join('teams', 'templates', 'teams'),
    os.path.join('strategy', 'templates', 'strategy')
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": UI_TEMPLATES,
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "scouting_backend.context_processors.config_context",
            ],
        },
    },
]

WSGI_APPLICATION = 'scouting_backend.wsgi.application'

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=0,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 20,
            }
        }
    }

# Static files configuration
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'frontend', 'dist'),  # Built assets from webpack
    os.path.join(BASE_DIR, 'static'),
    os.path.join(BASE_DIR, 'scanner', 'static'),
    os.path.join(BASE_DIR, 'teams', 'static'),
    os.path.join(BASE_DIR, 'strategy', 'static'),
]

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Whitenoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
LOGIN_REDIRECT_URL = '/'

LOGIN_URL= '/auth/'

# Crispy Forms settings
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

# Cookie security - always enforced regardless of DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Must be False so JS can read the token for AJAX requests

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# Security settings for production
if not DEBUG:
    # Proxy SSL configuration - fixes OAuth redirect_uri_mismatch
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
