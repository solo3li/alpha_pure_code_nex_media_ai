from pathlib import Path
from dotenv import load_dotenv
from os import getenv, path
from loguru import logger
from datetime import timedelta, date
import cloudinary



# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent

APPS_DIR = BASE_DIR / "core_apps"
LOGURU_LOGGING = {
    "handlers":[
        {
            "sink": BASE_DIR / "logs/debug.log",
            "level": "DEBUG",
            "filter": lambda record: record["level"].no <= logger.level("WARNING").no,
            "format": "{time:YYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            "rotation": "10MB",
            "retention": "30 days",
            "compression": "zip",
        },
        {
            "sink": BASE_DIR / "logs/error.log",
            "level": "ERROR",
            "format": "{time:YYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            "rotation": "10MB",
            "retention": "30 days",
            "compression": "zip",
            "backtrace": True,
            "diagnose": True,
        },

    ],

}

logger.configure(**LOGURU_LOGGING)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "loguru": {
            "class": "interceptor.InterceptHandler"
            }
        },
    "root": {
        "handlers": ["loguru"],
        "level": "DEBUG"
        },
}

local_env_file = path.join(BASE_DIR, ".env", ".env.local")
if path.isfile(local_env_file):
    load_dotenv(local_env_file)

RECAPTCHA_PUBLIC_KEY = '6LfDmt4rAAAAAMoq9v_Jh8r5FE2Vz4fXUjJ1SJZS'
RECAPTCHA_PRIVATE_KEY = '6LfDmt4rAAAAAPHU1z0d476Ln3LOxLaEHwJ5x-69'
# Application definition

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django_recaptcha'
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_countries",
    "phonenumber_field",
    "drf_spectacular",
    "cloudinary",
    "django_filters",
    "djcelery_email",
    "django_celery_beat",
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',  
    
    'captcha',
    'rest_framework.authtoken',
    'django_extensions',
    
]
import os
AUDIO_STORAGE_PATH = os.path.join(BASE_DIR, 'media', 'audio_files')

# Ensure the directory exists
os.makedirs(AUDIO_STORAGE_PATH, exist_ok=True)

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
RECAPTCHA_PUBLIC_KEY = '6LchzewqAAAAABfeOqSgbh7XT68YMvf4AI_aD_Lc'
RECAPTCHA_PRIVATE_KEY = '6LchzewqAAAAAAGOoCz_ohVyEVzXNiQm3DQtRnCP'


# Platform Partner App - 5325396000821058853
# Payment settings

# test 
# PAYPAL_CLIENT_ID = 'AUudGskris19cSQ6X3cCyiFhmH-Dut3Dodmdw1jeMhN5OgW6GMonIsTvsuBNPOCL_fQbApqgoewVdjk2'
# PAYPAL_CLIENT_SECRET = 'EJ6Ka_bmbBni3UC1MLPMM-JZtU0elP0clL5rsHOGRCNq6meRf4QOtnQEi7CHlKMRCPnU89DvhoJ4ZoeW'
# PAYPAL_API_BASE = 'https://api-m.sandbox.paypal.com'  

# test arabic not
# PAYPAL_CLIENT_ID = 'AbZF7L2Yt-7s3kbs6Aahy1EzVX5ljfZ1PDtBb3L-t8zv5U32lhld4f9RHuuidNhPS2U2L32OJsv3eZw6'
# PAYPAL_CLIENT_SECRET = 'EFM3yO_NT2u4kyYsMV82YMlwMinHkFBH9eTPMKPbmbHZ49_P934GHD1rek_WdNoKlBAmapvxyNDA3OXN'
# PAYPAL_API_BASE = 'https://api-m.sandbox.paypal.com'  


# test english working
# PAYPAL_CLIENT_ID = 'ARjmGWCzZOQte5ev7zNvng8eTjtoHSdkWelVbPmI_fHqu3dXua5gtiM-udVH1AD0RP_5FhSUCfV-I7sO'
# PAYPAL_CLIENT_SECRET = 'EKpEhtnvWuz4Mu1mYQEqhMUh8wu33n152-fzQ0h1QHqoDU8OXbap7l3skGsUqNvTuHDqKf0xNXkHJ0QX'
# PAYPAL_API_BASE = 'https://api-m.sandbox.paypal.com'  

# live
PAYPAL_CLIENT_ID = 'AekBB_ovxpPk3OYStoC65R8Wa0CKSmLiOdSUkLOyQVnKukeokGWyPSdDBMjyJjAQBoeV5iXlUx1vKhhL'
PAYPAL_CLIENT_SECRET = 'EDSZ7xcVufn7n_De3xRzFNfGXAi5SWKCaI9hI5OM_tUm_SvWncq6fQqexFX6YodWykQ9WrDO1-4tVobE'
PAYPAL_API_BASE = "https://api-m.paypal.com"

# live
PAYMOB_SECRET_KEY = getenv('PAYMOB_SECRET_KEY', '')
PAYMOB_PUBLIC_KEY = 'egy_pk_live_zmBCF0drrgwVhd5Z6BeI5hnBeTCHz2CC'

# PAYMOB_INTEGRATION_ID = 4927392  # Your Paymob integration ID

# PAYMOB_WALLET_INTEGRATION_ID = 4933289  # Your Paymob wallet integration ID
PAYMOB_API_KEY = 'ZXlKaGJHY2lPaUpJVXpVeE1pSXNJblI1Y0NJNklrcFhWQ0o5LmV5SmpiR0Z6Y3lJNklrMWxjbU5vWVc1MElpd2ljSEp2Wm1sc1pWOXdheUk2TVRBeE9ERXlOaXdpYm1GdFpTSTZJbWx1YVhScFlXd2lmUS5iNmozSzUyQ0c0YzZzMk9UdXE0QnAzQ2UzajhFeHN5NmlqM0U5Wk9DRkVMS0lmZkZGZ2RmajByTUN3ZGZhdWt4NXBXU3RuaWQ4XzY5eWYwMDNmLWg5UQ=='

SIGNING_SECRET = 'your-signing-secret'  # For generating/validating signatures
BASE_URL = 'https://nexmediaai.com/'  # Your base URL for webhooks


LOCAL_APPS = [

    "core_apps.user_auth",
    'core_apps.subscriptions',
    'core_apps.tools',
    'core_apps.tool_data',
    'core_apps.plan_tools',
    'core_apps.home',
    'core_apps.user_profile',
    'core_apps.history',

    'web_apps.bg_remover',
    'web_apps.v_bg_remover',
    'web_apps.video_caption',
    'web_apps.img_to_txt',
    'web_apps.voice_to_text',
    'web_apps.text_to_cartoon',
    'web_apps.gpt',
    'web_apps.text_to_voice',
    'web_apps.make_my_trip',
    # 'core_admin'
]

FLASK_SERVICE_API_KEY = 'GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf'

APPEND_SLASH = True
AUTHENTICATION_BACKENDS = (
    'core_apps.user_auth.backends.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',                
)                   
GOOGLE_CLIENT_ID = getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = getenv('GOOGLE_CLIENT_SECRET', '')

# Google OAuth2 settings for custom implementation
GOOGLE_OAUTH2_CONFIG = {
    'client_id': GOOGLE_CLIENT_ID,
    'client_secret': GOOGLE_CLIENT_SECRET,
    'scope': 'openid email profile',
    'redirect_uri': 'https://nexmediaai.com/accounts/google/callback/',
}

# Custom authentication forms
AUTH_FORMS = {
    'signup': 'core_apps.user_auth.forms.CustomRegistrationForm',
    'login': 'core_apps.user_auth.forms.CustomLoginForm',
}

# Authentication URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/home/'
LOGOUT_REDIRECT_URL = '/login/'

# Email verification settings
EMAIL_VERIFICATION_EXPIRE_DAYS = 3
EMAIL_VERIFICATION_REDIRECT_URL = "/email-confirmation-sent/"



INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS



# Custom authentication settings
AUTH_USER_MODEL_USERNAME_FIELD = None
AUTH_AUTHENTICATION_METHOD = 'email'
AUTH_EMAIL_REQUIRED = True
AUTH_USERNAME_REQUIRED = False
AUTH_UNIQUE_EMAIL = True
AUTH_EMAIL_VERIFICATION = 'mandatory'
AUTH_LOGIN_ATTEMPTS_LIMIT = 5
AUTH_LOGIN_ATTEMPTS_TIMEOUT = 300

# Site ID
SITE_ID = 1



MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',   # ← must be after Session, before Common
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core_apps.user_auth.middleware.CustomHeaderMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",       # global templates (admin overrides, base layouts, etc.)
            APPS_DIR / "templates",       # if you keep a shared templates folder under apps
        ],
        "APP_DIRS": True,                 # also loads templates inside each app automatically
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core_apps.subscriptions.context_processors.paypal_settings",
            ],
        },
    },
]


WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": getenv("POSTGRES_DB"),
        "USER": getenv("POSTGRES_USER"),
        "PASSWORD": getenv("POSTGRES_PASSWORD"),
        "HOST": getenv("POSTGRES_HOST"),
        "PORT": getenv("POSTGRES_PORT"),
    }
}


PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = 'en'

LANGUAGES = [
    ('en', _('English')),
    ('ar', _('Arabic')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

TIME_ZONE = 'UTC'

USE_I18N = True
USE_L10N = True
USE_TZ = True



# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [str(BASE_DIR / "static")]
STATIC_ROOT = str(BASE_DIR / "staticfiles")

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING_CONFIG = None

CLOUDINARY_CLOUD_NAME = getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = getenv("CLOUDINARY_API_SECRET")
# Authentication behavior
AUTH_LOGOUT_ON_GET = True
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
)


COOKIE_NAME = "access"
COOKIE_SAME_SITE = "Lax"
COOKIE_PATH = "/"
COOKIE_HTTP_ONLY = True
COOKIE_SECURE = getenv("COOKIE_SECURE", "True") == True



AUTH_USER_MODEL = "user_auth.USER"
DEFAULT_BIRTH_DATE = date(1900,1,1)
DEFAULT_DATE = date(2000,1,1)
DEFAULT_EXPIRY_DATE = date(2024,1,1)
DEFAULT_COUNTRY = "EG"
DEFAULT_PHONE_NUMBER = "+201553963637"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        'rest_framework.authentication.SessionAuthentication',
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "PAGE_SIZE": 10,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/day",
        "user": "200/day",
    },
}

SIMPLE_JWT = {
    "SIGNING_KEY": getenv("SIGNING_KEY"),
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,  # Add this line
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}


SPECTACULAR_SETTINGS = {
    "TITLE": "NEXMEDIA API",
    "DESCRIPTION": "An API built for NexMedia",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "LICENSE": {
        "name": "MIT License",
        "url": "https://opensource.org/license/mit",
    },
}

# CELERY_BEAT_SCHEDULE={
#     "apply_daily_interest": {
#         "task": "core_apps.accounts.tasks.apply_daily_interest",
#     },
#     "detect_sus_activities": {
#         "task": "core_apps.accounts.tasks.detect_suspicious_activities",
#     },
# }
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'cleanup-old-processing': {
        'task': 'web_apps.v_bg_remover.tasks.cleanup_old_processing',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'handle-stuck-processes': {
        'task': 'web_apps.v_bg_remover.tasks.handle_stuck_processes',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    'handle-stuck-caption-processes': {
        'task': 'web_apps.video_caption.tasks.handle_stuck_processes',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    'handle-stuck-cartoon-processes': {
        'task': 'web_apps.text_to_cartoon.tasks.handle_stuck_processes',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },

    'cleanup-old-tts-files-daily': {
        'task': 'web_apps.text_to_voice.tasks.cleanup_old_tts_files',
        'schedule': crontab(hour=3, minute=0),
    },
}

CELERY_BROKER_URL = getenv("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = getenv("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
CELERY_TASK_TIME_LIMIT = 5 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 60
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_WORKER_SEND_TASK_EVENTS = True

# Add to your existing settings.py

# --- PayPal Specific Settings ---
# 1. Content Security Policy & Security Headers
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups' 