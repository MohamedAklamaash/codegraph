from django.urls import path

from .views import GraphView

urlpatterns = [
    path("<uuid:repo_id>/", GraphView.as_view()),
]
