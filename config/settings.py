"""
Configuración del proyecto Dulce Arte.
Sistema de Trazabilidad y Pedidos para Pastelería Artesanal.
"""

from pathlib import Path

import environ

# Ruta base del proyecto (la carpeta EVA3_Backend)
BASE_DIR = Path(__file__).resolve().parent.parent

# Lectura de variables de entorno desde el archivo .env
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')


# ---------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------
SECRET_KEY = env('SECRET_KEY')

DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])


# ---------------------------------------------------------------
# Aplicaciones instaladas
# ---------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Librerías externas
    'rest_framework',
    'drf_spectacular',
    # Apps del proyecto Dulce Arte
    'inventario',
    'pedidos',
    'despachos',
    'web',
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

ROOT_URLCONF = 'config.urls'

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
                'web.context_processors.roles',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ---------------------------------------------------------------
# Base de datos: PostgreSQL (datos leídos desde .env)
# ---------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
    }
}


# ---------------------------------------------------------------
# Validación de contraseñas
# ---------------------------------------------------------------
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


# ---------------------------------------------------------------
# Idioma y zona horaria (Chile)
# ---------------------------------------------------------------
LANGUAGE_CODE = 'es-cl'

TIME_ZONE = 'America/Santiago'

USE_I18N = True

USE_TZ = True


# ---------------------------------------------------------------
# Archivos estáticos (CSS, JavaScript, imágenes del diseño)
# ---------------------------------------------------------------
STATIC_URL = 'static/'


# ---------------------------------------------------------------
# Archivos subidos por usuarios (fotos de productos, firmas, comprobantes)
# ---------------------------------------------------------------
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ---------------------------------------------------------------
# Inicio y cierre de sesión de la interfaz web
# ---------------------------------------------------------------
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'inicio'
LOGOUT_REDIRECT_URL = 'login'


# ---------------------------------------------------------------
# Django REST Framework (API)
# ---------------------------------------------------------------
REST_FRAMEWORK = {
    # La interfaz web usa la misma sesión de Django (login con usuario y contraseña).
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    # Por defecto, toda la API exige haber iniciado sesión.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'API Dulce Arte',
    'DESCRIPTION': 'Sistema de Trazabilidad y Pedidos para Pastelería Artesanal.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # La documentación solo es visible con sesión iniciada.
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticated'],
    # Nombres claros para los distintos "estado" en la documentación.
    'ENUM_NAME_OVERRIDES': {
        'EstadoPedidoEnum': 'pedidos.models.Pedido.Estado',
        'EstadoDespachoEnum': 'despachos.models.Despacho.Estado',
        'EstadoRutaEnum': 'despachos.models.Ruta.Estado',
    },
}


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
