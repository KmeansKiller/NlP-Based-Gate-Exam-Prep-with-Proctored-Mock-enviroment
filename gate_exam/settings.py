import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'your-secret-key'  # Replace with a secure random key

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'exam',  # Our application
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gate_exam.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'exam', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gate_exam.wsgi.application'

DATABASES = {
    'default': {
         'ENGINE': 'django.db.backends.sqlite3',
         'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'exam', 'static')]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/exam/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# (Inside gate_exam/settings.py)

import os # Ensure os is imported
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ... (Keep existing settings like SECRET_KEY, DEBUG, INSTALLED_APPS, etc.) ...

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'exam', 'static')]

# --- Add Media file settings ---
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media') # Creates a 'media' folder in your project root
# ------------------------------

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/exam/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# gate_exam/settings.py
# ... other settings ...

TWOFACTOR_API_KEY = '669ecb2f-0f96-11f0-8b17-0200cd936042' # Replace with your actual key