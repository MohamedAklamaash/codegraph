from django.urls import path

from .views import GraphView, TraceView

urlpatterns = [
    path("<uuid:repo_id>/", GraphView.as_view()),
    path("<uuid:repo_id>/trace/<int:node_id>/", TraceView.as_view()),
]
