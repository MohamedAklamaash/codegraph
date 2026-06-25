"""URLconf used in tests.

Mounts the repos / auth_github / files / graph / chat URL modules. The
files/graph/chat views import postgres-only model fields (ArrayField,
pgvector.VectorField); those imports are stubbed in conftest.py at process
start so the modules can be loaded under SQLite. Tests for those views
hit the access-gating path (404) and never query the postgres-only models.
"""
from django.urls import include, path

urlpatterns = [
    path("api/", include("apps.auth_github.urls")),
    path("api/repos/", include("apps.repos.urls")),
    path("api/files/", include("apps.files.urls")),
    path("api/graph/", include("apps.graph.urls")),
    path("api/chat/", include("apps.chat.urls")),
]
