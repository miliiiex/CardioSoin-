import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Variables locales (.env) — ne pas versionner backend/.env
_env_file = BASE_DIR / ".env"
if _env_file.is_file():
    from backend.env_loader import load_env_file

    load_env_file(_env_file, override=False)
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file, override=False)
    except ImportError:
        pass

# SECURITY
SECRET_KEY = 'django-insecure-change-this-key'

# Chiffrement at-rest des champs sensibles (DossierMedical) — django-encrypted-model-fields
# En production : générer une clé Fernet (32 octets, base64) et la passer en variable d’environnement.
import base64
import hashlib
from functools import lru_cache


@lru_cache(maxsize=1)
def _field_encryption_key() -> str:
    raw = os.environ.get("FIELD_ENCRYPTION_KEY")
    if raw:
        return raw
    seed = (SECRET_KEY + "enc-cardiosoin").encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(seed).digest()).decode("ascii")


FIELD_ENCRYPTION_KEY = _field_encryption_key()

DEBUG = True

# Évite « CSRF token incorrect » si tu passes entre localhost, 127.0.0.1 ou un autre hôte (Django 4+).
# En production : ex. https://mondomaine.com (avec le schéma).
def _default_csrf_trusted_origins() -> list[str]:
    """
    En dev, beaucoup d'erreurs « CSRF token incorrect » viennent d'un autre
    hôte (IP LAN, autre port) non listé, ou d'une page de connexion en cache.
    On couvre 127.0.0.1 / localhost / ::1 sur les ports de runserver fréquents.
    En prod : surcharger DJANGO_CSRF_TRUSTED_ORIGINS ou cette liste.
    """
    o: list[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://[::1]:8000",
    ]
    for port in (8000, 8001, 8080, 3000, 5000, 80):
        for host in (
            "http://127.0.0.1",
            "http://localhost",
            "http://[::1]",
        ):
            u = f"{host}:{port}"
            if u not in o:
                o.append(u)
    return o


CSRF_TRUSTED_ORIGINS = _default_csrf_trusted_origins()
_extra_csrf = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
if _extra_csrf:
    for o in _extra_csrf.split(","):
        o = o.strip()
        if o and o not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(o)

# Jeton CSRF dans un cookie « csrftoken » (recommandé avec formulaires publics / landing).
# CSRF_USE_SESSIONS=True provoque souvent « CSRF cookie not set » si la session n’est pas encore créée.
CSRF_USE_SESSIONS = False
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "accounts.views.csrf_failure"

# Requis dès le premier en-tête Host (navigateur, tests, runserver). En prod : DJANGO_ALLOWED_HOSTS=domain1,domain2
_default_hosts = "localhost,127.0.0.1,testserver,[::1]"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", _default_hosts).split(",") if h.strip()]

# Applications
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # tes apps
    'accounts',
    'appointments',
    'patients',
    'prescriptions',
    'cabinet',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# URLs
ROOT_URLCONF = 'backend.urls'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR.parent, 'templates')],  # si tu as un dossier templates
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.csrf',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.email_setup',
            ],
        },
    },
]

# WSGI
WSGI_APPLICATION = 'backend.wsgi.application'

# Base de données — MySQL (WAMP) par défaut ; base `pfa_medical` comme dans phpMyAdmin
# Variables d'environnement optionnelles : MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT
# Repasse sur SQLite : définir DJANGO_USE_SQLITE=1
if os.environ.get("DJANGO_USE_SQLITE") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR.parent / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("MYSQL_DATABASE", "pfa_medical"),
            "USER": os.environ.get("MYSQL_USER", "root"),
            "PASSWORD": os.environ.get("MYSQL_PASSWORD", ""),
            "HOST": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.environ.get("MYSQL_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = []

# Language / Time
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'

# Racine `pfa project/static` + `backend/static`
STATICFILES_DIRS = [
    str(BASE_DIR.parent / 'static'),
    str(BASE_DIR / 'static'),
]

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Fichiers uploadés (photo profil personnel cabinet)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'

# Aligné sur `path("login/", ...)` (la valeur Django par défaut est `/accounts/login/`).
LOGIN_URL = "login"

AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailOrUsernameBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# E-mail — SMTP réel si identifiants valides dans .env, sinon console (dev)
_PLACEHOLDER_EMAIL_USERS = frozenset(
    {"", "votre.adresse@gmail.com", "change-me@example.com"}
)
_PLACEHOLDER_EMAIL_PASSWORDS = frozenset(
    {
        "",
        "votre_mot_de_passe_application_16_caracteres",
        "changeme",
    }
)


def _normalize_smtp_credential(raw: str, placeholders: frozenset[str]) -> str:
    value = (raw or "").strip()
    return "" if value.lower() in placeholders else value


_EMAIL_USER = _normalize_smtp_credential(
    os.environ.get("EMAIL_HOST_USER", ""), _PLACEHOLDER_EMAIL_USERS
)
_EMAIL_PASS = _normalize_smtp_credential(
    os.environ.get("EMAIL_HOST_PASSWORD", ""), _PLACEHOLDER_EMAIL_PASSWORDS
)
if not _EMAIL_PASS:
    _EMAIL_PASS = _normalize_smtp_credential(
        os.environ.get("GMAIL_APP_PASSWORD", ""), _PLACEHOLDER_EMAIL_PASSWORDS
    )
if not _EMAIL_PASS:
    _secret_path = BASE_DIR / "email_secret.txt"
    if _secret_path.is_file():
        _EMAIL_PASS = _normalize_smtp_credential(
            _secret_path.read_text(encoding="utf-8"), _PLACEHOLDER_EMAIL_PASSWORDS
        )
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.environ.get(
    "RESEND_FROM_EMAIL", "CardioSoin <onboarding@resend.dev>"
)
_smtp_ready = bool(_EMAIL_USER and _EMAIL_PASS)
_default_email_backend = (
    "django.core.mail.backends.smtp.EmailBackend"
    if _smtp_ready
    else "django.core.mail.backends.console.EmailBackend"
)
_env_backend = os.environ.get("EMAIL_BACKEND", "").strip()
if _env_backend and _smtp_ready:
    EMAIL_BACKEND = _env_backend
elif _env_backend and "console" in _env_backend.lower():
    EMAIL_BACKEND = _env_backend
else:
    EMAIL_BACKEND = _default_email_backend
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = _EMAIL_USER
EMAIL_HOST_PASSWORD = _EMAIL_PASS
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "30"))
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    f"CardioSoin <{_EMAIL_USER}>" if _EMAIL_USER else "CardioSoin <noreply@cardiosoin.local>",
)
EMAIL_VERIFICATION_CODE_MINUTES = int(
    os.environ.get("EMAIL_VERIFICATION_CODE_MINUTES", "15")
)
EMAIL_VERIFICATION_SESSION_MINUTES = int(
    os.environ.get("EMAIL_VERIFICATION_SESSION_MINUTES", "45")
)