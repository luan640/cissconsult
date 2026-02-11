import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def get_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {
        '1',
        'true',
        't',
        'yes',
        'y',
        'on',
    }


load_env_file(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'change-this-before-production')

# SECURITY WARNING: do not enable debug mode in production.
DEBUG = get_bool('DJANGO_DEBUG', True)

def _get_csv_env(name: str) -> list[str]:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(',') if item.strip()]


ALLOWED_HOSTS = [
    '127.0.0.1',
    ".trycloudflare.com",
    ".onrender.com",
]
ALLOWED_HOSTS += _get_csv_env('DJANGO_ALLOWED_HOSTS')

CSRF_TRUSTED_ORIGINS = [
    "https://*.trycloudflare.com",
]
CSRF_TRUSTED_ORIGINS += [
    f"https://{host}"
    for host in _get_csv_env('DJANGO_ALLOWED_HOSTS')
    if host and not host.startswith('.')
]
CSRF_TRUSTED_ORIGINS += ["https://*.onrender.com"]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'masterdata.apps.MasterdataConfig',
    'apps.tenancy.apps.TenancyConfig',
    'apps.core.apps.CoreConfig',
]

if DEBUG:
    INSTALLED_APPS += [
        'debug_toolbar',
    ]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.tenancy.middleware.CompanyContextMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_MANIFEST_STRICT = False

if DEBUG:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    MIDDLEWARE.append('ciss_gestao.middleware.RequestTimingMiddleware')

ROOT_URLCONF = 'ciss_gestao.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ciss_gestao.context_processors.current_company',
            ],
        },
    },
]

WSGI_APPLICATION = 'ciss_gestao.wsgi.application'


DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.sqlite3')

if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / os.getenv('SQLITE_NAME', 'db.sqlite3'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': os.getenv('DB_NAME', 'plataforma_nr1'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = os.getenv('DJANGO_TIME_ZONE', 'America/Sao_Paulo')

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

USE_S3 = get_bool('USE_S3', False)

if USE_S3:
    INSTALLED_APPS += ['storages']
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', '')
    AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL', '')
    if AWS_S3_ENDPOINT_URL.endswith('/storage/v1/object/public'):
        AWS_S3_ENDPOINT_URL = AWS_S3_ENDPOINT_URL.replace('/storage/v1/object/public', '/storage/v1/s3')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', '')
    AWS_S3_ADDRESSING_STYLE = os.getenv('AWS_S3_ADDRESSING_STYLE', 'path')
    AWS_S3_SIGNATURE_VERSION = os.getenv('AWS_S3_SIGNATURE_VERSION', 's3v4')
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = get_bool('AWS_QUERYSTRING_AUTH', False)

    AWS_S3_PUBLIC_URL = os.getenv('AWS_S3_PUBLIC_URL', '').strip().rstrip('/')
    if AWS_S3_PUBLIC_URL:
        AWS_S3_CUSTOM_DOMAIN = AWS_S3_PUBLIC_URL.replace('https://', '').replace('http://', '')

    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

    MEDIA_URL = (AWS_S3_PUBLIC_URL + '/companies/') if AWS_S3_PUBLIC_URL else (
        f"{AWS_S3_ENDPOINT_URL.rstrip('/')}/{AWS_STORAGE_BUCKET_NAME}/"
        if AWS_S3_ENDPOINT_URL and AWS_STORAGE_BUCKET_NAME
        else MEDIA_URL
    )

INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'cissconsult-local',
    }
}

TENANCY_COMPANY_HEADER = os.getenv('TENANCY_COMPANY_HEADER', 'X-Company-Id')
TENANCY_EXEMPT_PATH_PREFIXES = [
    '/admin/',
    '/auth/',
    '/healthz/',
    '/static/',
    '/media/',
    '/master/',
    '/campaigns/',
    '/__debug__/',
]

LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'
