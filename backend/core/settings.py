import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
DEBUG = os.environ.get("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Hard-fail on a placeholder SECRET_KEY in production. We only honor the
# default in DEBUG so dev workflows don't break.
if not DEBUG and SECRET_KEY in ("dev-secret", "your-secret-key-here"):
    raise ImproperlyConfigured(
        "SECRET_KEY must be set in production (got placeholder value)."
    )

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "rest_framework",
    "corsheaders",
    "apps.repos",
    "apps.files",
    "apps.parser",
    "apps.graph",
    "apps.embeddings",
    "apps.chat",
    "apps.auth_github",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

APPEND_SLASH = False

ROOT_URLCONF = "core.urls"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "knowledge_base"),
        "USER": os.environ.get("POSTGRES_USER", "kbuser"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "kbpass123"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/0"),
    }
}

REPOS_DIR = os.environ.get("REPOS_DIR", ".repos")
if not os.path.isabs(REPOS_DIR):
    REPOS_DIR = str(BASE_DIR / REPOS_DIR)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_OAUTH_REDIRECT_URI = os.environ.get(
    "GITHUB_OAUTH_REDIRECT_URI", "http://localhost:9000/api/auth/github/callback/"
)
GITHUB_TOKEN_ENC_KEY = os.environ.get("GITHUB_TOKEN_ENC_KEY", "")
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
