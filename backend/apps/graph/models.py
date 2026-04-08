from django.db import models
from django.contrib.postgres.fields import ArrayField
from apps.repos.models import Repository
from apps.files.models import RepoFile

class FunctionNode(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="functions")
    file = models.ForeignKey(RepoFile, on_delete=models.CASCADE, related_name="functions")
    name = models.CharField(max_length=255)
    start_line = models.IntegerField()
    end_line = models.IntegerField()
    source = models.TextField()
    summary = models.TextField(blank=True)
    calls = ArrayField(models.CharField(max_length=255), default=list)

    class Meta:
        unique_together = ("repository", "file", "name", "start_line")

    def __str__(self):
        return f"{self.file.path}::{self.name}"

class FunctionEdge(models.Model):
    EDGE_TYPES = [("CALLS", "Calls"), ("IMPORTS", "Imports")]

    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="edges")
    source = models.ForeignKey(FunctionNode, on_delete=models.CASCADE, related_name="outgoing")
    target = models.ForeignKey(FunctionNode, on_delete=models.CASCADE, related_name="incoming")
    edge_type = models.CharField(max_length=20, choices=EDGE_TYPES)

    class Meta:
        unique_together = ("source", "target", "edge_type")
