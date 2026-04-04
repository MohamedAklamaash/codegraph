from django.urls import path
from .views import RepositoryView

urlpatterns = [
    path("", RepositoryView.as_view()),
    path("<uuid:repo_id>/", RepositoryView.as_view()),
]
