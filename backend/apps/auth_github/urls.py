from django.urls import path

from .views import (
    CsrfView,
    GithubOAuthCallbackView,
    GithubOAuthStartView,
    GithubReposView,
    LogoutView,
    MeView,
)

urlpatterns = [
    path("auth/github/start/", GithubOAuthStartView.as_view()),
    path("auth/github/callback/", GithubOAuthCallbackView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/csrf/", CsrfView.as_view()),
    path("me/", MeView.as_view()),
    path("github/repos/", GithubReposView.as_view()),
]
