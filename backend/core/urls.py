from django.urls import include, path

urlpatterns = [
    path("api/repos/", include("apps.repos.urls")),
    path("api/graph/", include("apps.graph.urls")),
    path("api/chat/", include("apps.chat.urls")),
    path("api/files/", include("apps.files.urls")),
]
