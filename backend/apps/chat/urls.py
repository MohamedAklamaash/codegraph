from django.urls import path
from .views import ChatView

urlpatterns = [
    path("<uuid:repo_id>/", ChatView.as_view()),
]
