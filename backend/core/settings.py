import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "corsheaders",
    "apps.repos",
    "apps.files",
    "apps.parser",
    "apps.graph",
    "apps.embeddings",
    "apps.chat",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

CORS_ALLOW_ALL_ORIGINS = True
APPEND_SLASH = False

ROOT_URLCONF = "core.urls"

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

REPOS_DIR = os.environ.get("REPOS_DIR", "/repos")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
