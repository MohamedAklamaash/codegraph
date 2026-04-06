from django.db import models
from apps.repos.models import Repository

class RepoFile(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="files")
    path = models.CharField(max_length=1024)  # relative path within repo
    language = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("repository", "path")

    def __str__(self):
        return self.path
