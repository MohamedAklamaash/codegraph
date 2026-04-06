from django.urls import path
from .views import FileTreeView, FileFunctionsView

urlpatterns = [
    path("<uuid:repo_id>/tree/", FileTreeView.as_view()),
    path("<uuid:repo_id>/files/<int:file_id>/functions/", FileFunctionsView.as_view()),
]
