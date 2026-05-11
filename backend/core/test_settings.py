"""
Test settings: minimal Django config that runs against SQLite.

Loaded by pytest-django via `DJANGO_SETTINGS_MODULE=core.test_settings`
*before* `django.setup()` populates apps. We use that ordering to install
runtime stubs for postgres-only modules (pgvector, django.contrib.postgres,
google.generativeai) that the chat/graph/files/embeddings models import
at module load. The stubbed fields produce a `db_type` of TEXT under
SQLite; tests never query those models — they hit cross-tenant 404 first.
"""
import os
import sys
import types

# --- google.generativeai stub ----------------------------------------------
# The pinned google-generativeai version crashes on Py3.14 protobuf import
# and we never need the real client in unit tests. Both `apps.embeddings.client`
# and `apps.chat.views` / `apps.graph.views` import it at module level.
if "google" not in sys.modules:
    _google_pkg = types.ModuleType("google")
    _google_pkg.__path__ = []
    sys.modules["google"] = _google_pkg

if "google.generativeai" not in sys.modules:
    _genai_stub = types.ModuleType("google.generativeai")

    def _genai_configure(*args, **kwargs):
        return None

    def _genai_embed_content(*args, **kwargs):
        return {"embedding": [0.0]}

    class _GenerativeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            class _R:
                text = ""
            return _R()

    _genai_stub.configure = _genai_configure
    _genai_stub.embed_content = _genai_embed_content
    _genai_stub.GenerativeModel = _GenerativeModel
    sys.modules["google.generativeai"] = _genai_stub
    sys.modules["google"].generativeai = _genai_stub


# --- django.contrib.postgres.fields.ArrayField stub ------------------------
# `apps.graph.models` imports ArrayField at module load; the real package
# transitively imports psycopg2 which we don't ship in the test venv.
# We stub Django itself isn't yet imported here — but `from django...` triggers
# loading `django` and `django.db` only. We then poison the `postgres` subpath.
if "django.contrib.postgres" not in sys.modules:
    from django.db import models as _dj_models  # noqa: E402

    _pg_pkg = types.ModuleType("django.contrib.postgres")
    _pg_pkg.__path__ = []
    _pg_fields = types.ModuleType("django.contrib.postgres.fields")
    _pg_fields.__path__ = []

    import json as _json  # noqa: E402

    class _StubArrayField(_dj_models.Field):
        def __init__(self, base_field=None, size=None, **kwargs):
            # Default base_field so Django's `field.clone()` (which calls
            # __init__ with deconstructed args) doesn't fail.
            self.base_field = base_field
            self.size = size
            super().__init__(**kwargs)

        def db_type(self, connection):
            return "text"

        def get_prep_value(self, value):
            # Serialize lists as JSON for SQLite. Real ArrayField stores them
            # natively in postgres; the stub only needs to round-trip values
            # in-memory so tests that create rows don't blow up.
            if value is None:
                return None
            return _json.dumps(list(value))

        def from_db_value(self, value, expression, connection):
            if value is None or value == "":
                return []
            try:
                return _json.loads(value)
            except (ValueError, TypeError):
                return []

        def to_python(self, value):
            if value is None or isinstance(value, list):
                return value if value is not None else []
            try:
                return _json.loads(value)
            except (ValueError, TypeError):
                return []

        def deconstruct(self):
            name, path, args, kwargs = super().deconstruct()
            if self.size is not None:
                kwargs["size"] = self.size
            # Don't try to round-trip base_field through deconstruct — the
            # nested field would need its own deconstruct path. The stub is
            # only used so models can be created in-memory under SQLite.
            return name, path, args, kwargs

    class _StubHStoreField(_dj_models.Field):
        def db_type(self, connection):
            return "text"

    class _StubJSONField(_dj_models.Field):
        def db_type(self, connection):
            return "text"

    class _StubRangeField(_dj_models.Field):
        def db_type(self, connection):
            return "text"

    _pg_fields.ArrayField = _StubArrayField
    _pg_fields.HStoreField = _StubHStoreField
    _pg_fields.JSONField = _StubJSONField
    _pg_fields.RangeField = _StubRangeField
    sys.modules["django.contrib.postgres"] = _pg_pkg
    sys.modules["django.contrib.postgres.fields"] = _pg_fields
    _pg_pkg.fields = _pg_fields

    # Make sure `django.contrib.postgres` resolves to the stub via attribute
    # lookup (some import paths short-circuit via the parent package).
    import django.contrib  # noqa: E402
    django.contrib.postgres = _pg_pkg


# --- pgvector.django stub ---------------------------------------------------
# pgvector's __init__ imports django.contrib.postgres.operations which we
# can't load. The chat view imports `L2Distance`; the embeddings model uses
# `VectorField` at module load.
if "pgvector" not in sys.modules:
    _pgv = types.ModuleType("pgvector")
    _pgv.__path__ = []
    sys.modules["pgvector"] = _pgv

if "pgvector.django" not in sys.modules:
    from django.db import models as _dj_models2  # noqa: E402

    _pgv_django = types.ModuleType("pgvector.django")

    class _StubVectorField(_dj_models2.Field):
        def __init__(self, *args, dimensions=None, **kwargs):
            self.dimensions = dimensions
            super().__init__(*args, **kwargs)

        def db_type(self, connection):
            return "text"

        def deconstruct(self):
            name, path, args, kwargs = super().deconstruct()
            if self.dimensions is not None:
                kwargs["dimensions"] = self.dimensions
            return name, path, args, kwargs

    class _StubL2Distance:
        def __init__(self, *args, **kwargs):
            pass

    _pgv_django.VectorField = _StubVectorField
    _pgv_django.L2Distance = _StubL2Distance
    sys.modules["pgvector.django"] = _pgv_django
    sys.modules["pgvector"].django = _pgv_django


# Force sane env defaults BEFORE importing core.settings (which calls
# load_dotenv() and reads env vars at import time).
os.environ.setdefault("GITHUB_TOKEN_ENC_KEY", "")  # let individual tests set this
os.environ.setdefault("GITHUB_CLIENT_ID", "test_client_id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("GITHUB_OAUTH_REDIRECT_URI", "http://testserver/api/auth/github/callback/")
os.environ.setdefault("FRONTEND_BASE_URL", "http://localhost:5173")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("REPOS_DIR", "/tmp/codegraph-test-repos")

from core.settings import *  # noqa: E402,F401,F403

# Minimal apps -- only what the tests under test need.
# `apps.files`, `apps.graph`, `apps.chat`, `apps.embeddings` are added so the
# cross-app access-gating views can be loaded in `core.test_urls`. Their
# models use postgres-only fields (ArrayField/VectorField) which we stub
# pre-emptively in conftest.py; their migrations include `CREATE EXTENSION`
# SQL that doesn't run on SQLite, so we skip migrations entirely (tables are
# created by `--create-db` syncdb).
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "rest_framework",
    "corsheaders",
    "apps.repos",
    "apps.auth_github",
    "apps.files",
    "apps.graph",
    "apps.embeddings",
    "apps.chat",
]

# Skip migrations entirely so SQLite-incompatible operations
# (CREATE EXTENSION vector, etc) don't run. Tables are created by syncdb
# from the (stubbed-field) model definitions.
class _DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _DisableMigrations()

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Avoid hitting redis in tests.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Run celery tasks synchronously when invoked via .apply() — but we always
# patch .delay() in tests anyway. This is just belt-and-suspenders.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Fixed Fernet key for crypto tests that go through the regular path.
# Tests that need a missing key explicitly clear it via override_settings.
from cryptography.fernet import Fernet  # noqa: E402

GITHUB_TOKEN_ENC_KEY = Fernet.generate_key().decode()

# Use the trimmed test URLconf.
ROOT_URLCONF = "core.test_urls"

# Disable HTTPS cookie flags so the test client (HTTP) sets them.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Sentinel so callers can detect we are in test mode.
TESTING = True

# Use a fast password hasher in tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
